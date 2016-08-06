import json

print "hey"
RAW_RESPONSE = """
{
    "version": "1.0",
    "response": {
        "outputSpeech": {
            "type": "PlainText",
            "text": "Some default text goes here."
                },
        "shouldEndSession": False
    }
}"""


class Request(object):
    """
    Simple wrapper around the JSON request
    received by the module
    """
    def __init__(self, request_dict, metadata=None):
        self.request = request_dict
        self.metadata = metadata or {}
        self.session = self.request.get('session', {}).get('attributes', {})
        if self.intent_name():
            self.slots = self.get_slot_map()

    def request_type(self):
        return self.request["request"]["type"]

    def intent_name(self):
        if "intent" not in self.request["request"]:
            return None
        return self.request["request"]["intent"]["name"]

    def is_intent(self):
        if self.intent_name() is None:
            return False
        return True

    def user_id(self):
        return self.request["session"]["user"]["userId"]

    def access_token(self):
        try:
            return self.request['session']['user']['accessToken']
        except:
            return None

    def session_id(self):
        return self.request["session"]["sessionId"]

    def get_slot_value(self, slot_name):
        try:
            return self.request["request"]["intent"]["slots"][slot_name]["value"]
        except:
            """Value not found"""
            return None

    def get_slot_names(self):
        try:
            return self.request['request']['intent']['slots'].keys()
        except:
            return []

    def get_slot_map(self):
        return {slot_name: self.get_slot_value(slot_name)
                for slot_name in self.get_slot_names()}


class Response(object):
    def __init__(self, json_obj):
        self.json_obj = json_obj

    def __repr__(self):
        return json.dumps(self.json_obj, indent=4)

    def with_card(self, title, content, subtitle, card_type='Simple'):
        new_obj = dict(self.json_obj)
        new_obj['response']['card'] = ResponseBuilder.create_card(title, content,
                                                                        subtitle, card_type)
        return Response(new_obj)

    def with_reprompt(self, message, is_ssml):
        new_obj = dict(self.json_obj)
        new_obj['response']['reprompt'] = ResponseBuilder.create_speech(message, is_ssml)
        return Response(new_obj)

    def set_session(self, session_attr):
        self.json_obj['sessionAttributes'] = session_attr

    def to_json(self):
        return dict(self.json_obj)


class ResponseBuilder(object):
    """
    Simple class to help users to build responses
    """
    base_response = eval(RAW_RESPONSE)

    @classmethod
    def create_response(self, message=None, end_session=False, card_obj=None,
                        reprompt_message=None, is_ssml=None):
        """
        message - text message to be spoken out by the Echo
        end_session - flag to determine whether this interaction should end the session
        card_obj = JSON card object to substitute the 'card' field in the raw_response
        """
        response = dict(self.base_response)
        if message:
            response['response'] = self.create_speech(message, is_ssml)
        response['response']['shouldEndSession'] = end_session
        if card_obj:
            response['response']['card'] = card_obj
        if reprompt_message:
            response['response']['reprompt'] = self.create_speech(reprompt_message, is_ssml)
        return Response(response)

    @classmethod
    def respond(self, *args, **kwargs):
        return self.create_response(*args, **kwargs)

    @classmethod
    def create_speech(self, message=None, is_ssml=False):
        data = {}
        if is_ssml:
            data['type'], data['ssml'] = "SSML", message
        else:
            data['type'] = "PlainText"
            data['text'] = message
        return {"outputSpeech": data}

    @classmethod
    def create_card(self, title=None, subtitle=None, content=None, card_type="Simple"):
        """
        card_obj = JSON card object to substitute the 'card' field in the raw_response
        format:
        {
          "type": "Simple", #COMPULSORY
          "title": "string", #OPTIONAL
          "subtitle": "string", #OPTIONAL
          "content": "string" #OPTIONAL
        }
        """
        card = {"type": card_type}
        if title: card["title"] = title
        if subtitle: card["subtitle"] = subtitle
        if content: card["content"] = content
        return card


class VoiceHandler(ResponseBuilder):
    """    Decorator to store function metadata
    Functions that are annotated with this label are
    treated as voice handlers """

    def __init__(self):
        """
        >>> alexa = VoiceHandler()
        >>> request =
        >>> @alexa.intent('HelloWorldIntent')
        ... def hello_world(request):
        ...   return alexa.create_response('hello world')
        >>> alexa.route_request(request)
        """
        self._handlers = { "IntentRequest" : {} }
        self._default = '_default_'

    def default(self, func):
        ''' Decorator to register default handler '''

        self._handlers[self._default] = func

        return func

    def intent(self, intent):
        ''' Decorator to register intent handler'''

        def _handler(func):
            self._handlers['IntentRequest'][intent] = func
            return func

        return _handler

    def request(self, request_type):
        ''' Decorator to register generic request handler '''

        def _handler(func):
            self._handlers[request_type] = func
            return func

        return _handler

    def route_request(self, request_json, metadata=None):

        ''' Route the request object to the right handler function '''
        request = Request(request_json)
        request.metadata = metadata
        # add reprompt handler or some such for default?
        handler_fn = self._handlers[self._default] # Set default handling for noisy requests

        if not request.is_intent() and (request.request_type() in self._handlers):
            '''  Route request to a non intent handler '''
            handler_fn = self._handlers[request.request_type()]

        elif request.is_intent() and request.intent_name() in self._handlers['IntentRequest']:
            ''' Route to right intent handler '''
            handler_fn = self._handlers['IntentRequest'][request.intent_name()]

        response = handler_fn(request)
        response.set_session(request.session)
        return response.to_json()


alexa = VoiceHandler()
aResponse = ResponseBuilder()

def lambda_handler(request_obj, context=None):
    '''
    This is the main function to enter to enter into this code.
    If you are hosting this code on AWS Lambda, this should be the entry point.
    Otherwise your server can hit this code as long as you remember that the
    input 'request_obj' is JSON request converted into a nested python object.
    '''

    metadata = {'user_name' : 'SomeRandomDude'} # add your own metadata to the request using key value pairs

    ''' inject user relevant metadata into the request if you want to, here.
    e.g. Something like :
    ... metadata = {'user_name' : some_database.query_user_name(request.get_user_id())}
    Then in the handler function you can do something like -
    ... return alexa.create_response('Hello there {}!'.format(request.metadata['user_name']))
    '''
    return alexa.route_request(request_obj, metadata)

@alexa.default
def default_handler(request):
    """ The default handler gets invoked if no handler is set for a request type """
    return aResponse.respond('Just ask')


@alexa.request('LaunchRequest')
def launch_request_ha
ndler(request):
    ''' Handler for LaunchRequest '''
    return aResponse.create_response(message="Hello Welcome to My Recipes!")


@alexa.request("SessionEndedRequest")
def session_ended_request_handler(request):
    return aResponse.create_response(message="Goodbye!")


@alexa.intent('GetRecipeIntent')
def get_recipe_intent_handler(request):
    """
    You can insert arbitrary business logic code here
    """

    # Get variables like userId, slots, intent name etc from the 'Request' object
    ingredient = request.slots["Ingredient"]  # Gets an Ingredient Slot from the Request object.

    if ingredient == None:
        return aResponse.create_response("Could not find an ingredient!")

    # All manipulations to the request's session object are automatically reflected in the request returned to Amazon.
    # For e.g. This statement adds a new session attribute (automatically returned with the response) storing the
    # Last seen ingredient value in the 'last_ingredient' key.

    request.session['last_ingredient'] = ingredient # Automatically returned as a sessionAttribute

    # Modifying state like this saves us from explicitly having to return Session objects after every response

    # alexa can also build cards which can be sent as part of the response
    card = aResponse.create_card(title="GetRecipeIntent activated", subtitle=None,
                             content="asked alexa to find a recipe using {}".format(ingredient))

    return aResponse.create_response("Finding a recipe with the ingredient {}".format(ingredient),
                                 end_session=False, card_obj=card)



@alexa.intent('NextRecipeIntent')
def next_recipe_intent_handler(request):
    """
    You can insert arbitrary business logic code here
    """
    return aResponse.create_response(message="Getting Next Recipe ... 123")


if __name__ == "__main__":
    app.run(debug=True)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve','-s', action='store_true', default=False)
    args = parser.parse_args()
