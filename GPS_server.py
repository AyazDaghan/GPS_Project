from asyncio import constants
import logging
from math import radians, sin, cos, sqrt, atan2
import asyncio
from pickle import FALSE
import aiocoap
import aiocoap.resource as resource
from aiocoap.numbers import constants
import googlemaps
import re
import html
import datetime
import hashlib



gmaps = googlemaps.Client(key='AIzaSyC2JgwnTDFah4hCTwdeK9DVhWtrW_5eDFM')
    #For convert HTML codes to the normal characters
def clean_html_text(text):
    # Convert HTML entities like &amp; to normal characters
    unescaped_text = html.unescape(text)
    # Use regex to strip out any remaining HTML tags
    clean_text = re.sub(r'<.*?>', '', unescaped_text)
    return clean_text

    #Used Haversine Formula for determine distance between two points on a sphere given their longitudes and latitudes
def haversine_formula(lat1, lon1, lat2, lon2):
    R = 6371 # Eart radius type of Kilometer

    dlat = radians(lat2-lat1) #convert degrees to radians
    dlon = radians(lon2-lon1) #convert degrees to radians

    x = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    y = 2 * atan2(sqrt(x), sqrt(1-x))

    return R*y    

    #For indicate are users inside or outside of the our center
def is_inside_or_oustide_circle(client_lat, client_lon, center_lat, center_lon, radius):
    distance = haversine_formula(client_lat, client_lon, center_lat, center_lon)

    #If distance between center and user's current location less than our distance.
    #That means he/she is inside of the circle and if more than our distance, he/she is outside of the circle.
    return distance <= radius

    #if "Destination will be" is in the direction and insert a newline
def format_direction(direction):
    if "Destination will be" in direction:
        direction = direction.replace("Destination will be", "\nDestination will be")
    return direction
    
    #People who comes from outside of university
def get_direction_to_conf(client_lat, client_lon, mode):
    uni_location = (50.130654,8.692722)
    client_location = f"{client_lat},{client_lon}"

    #Client can choose the mode
    valid_modes = ["driving","walking","transit"]

    #They cannot choose modes that is not in the list
    if mode not in valid_modes:
        return f"This is not possible. Please choose from {', '.join(valid_modes)}."

    try:
        #With gmaps.direction method, we can get information about getting direction and mode
        directions_result = gmaps.directions(client_location, uni_location, mode=mode)

        if not directions_result:
            return "Can't get directions"
        #After reach the data, we choose the first route with [0]['legs'] and we choose only one direction with [0]['steps']
        steps = directions_result[0]['legs'][0]['steps']

        current_time = datetime.datetime.now()

        #For ETA(Estimated Time of Arrival)
        #For transit mode, ETA should be specific because of the transport's time
        if mode == "transit":
            eta = current_time
            for step in steps:
                if 'transit_details' in step:
                    # Use the provided arrival time for the step
                    eta = datetime.datetime.fromtimestamp(step['transit_details']['arrival_time']['value'])
                else:
                    # If it is walking, then add the step's duration
                    duration_in_minutes = int(step['duration']['value'] / 60)
                    eta += datetime.timedelta(minutes=duration_in_minutes)
        else:
            #For other modes
            duration_text = directions_result[0]['legs'][0]['duration']['text']
            duration_in_minutes = int(duration_text.split()[0])  # Assuming duration is always in minutes
            eta = current_time + datetime.timedelta(minutes=duration_in_minutes)

        eta_string = eta.strftime('%H:%M %p')
    

        #We extract necessary data in these statements
        if mode == "driving":
                directions = [f"{index+1:02}. Drive {step['distance']['text']} - {clean_html_text(step['html_instructions'])}" for index, step in enumerate(steps)]
        elif mode == "transit":
           directions = []
           counter = 1
           eta = current_time
           for step in steps:
              formatted_counter = f"{counter:02}"  # This ensures that numbers less than 10 will have a leading zero

              if 'transit_details' in step:
                   transit_type = step['transit_details']['line']['vehicle']['type']
                   transit_name = step['transit_details']['line'].get('short_name', step['transit_details']['line'].get('name', 'transit'))
                   direction = f"{formatted_counter}. Take {transit_type.capitalize()} {transit_name} for {step['distance']['text']} - {step['html_instructions']}"
              else:
                    direction = f"{formatted_counter}. Walk for {step['distance']['text']} - {step['html_instructions']}"

              counter += 1
              directions.append(direction)
        #Else for "walking"
        else: 
             directions = [f"{index+1:02}. {mode.capitalize()} for {step['distance']['text']} - {format_direction(clean_html_text(step['html_instructions']))}" for index, step in enumerate(steps)]

        # Insert ETA at the start of the directions list
        directions.insert(0, f"Estimated Time of Arrival (ETA): {eta_string}" +"\n")

        return '\n'.join(directions) + "\n\nWhen you reach the destination, please send request again."

    # Handling Exceptions Google Maps API exceptions 
    except googlemaps.exceptions.ApiError as e:
        return f"API error: {e}"
    except googlemaps.exceptions.HTTPError as e:
        return f"HTTP error: {e}"
    except googlemaps.exceptions.Timeout:
        return "Request to Google Maps timed out."
    except googlemaps.exceptions.TransportError:
        return "There was a transport error."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

    #People who are in university but outside of the building 4
def get_direction_from_inside(client_lat, client_lon, mode):
    building_location = (50.130671, 8.691818)
    client_location = f"{client_lat},{client_lon}"
    mode = "walking"

    try:
        directions_result = gmaps.directions(client_location, building_location, mode=mode)

        if not directions_result:
            return "Cant't get directions"

        steps = directions_result[0]['legs'][0]['steps']

        current_time = datetime.datetime.now()

        #For ETA(Estimad Time of Arrival)
        total_duration_in_seconds = sum([step['duration']['value'] for step in steps])
        eta = current_time + datetime.timedelta(seconds=total_duration_in_seconds)
        eta_string = eta.strftime('%H:%M %p')

        directions = [f"{index+1}. Walk for {step['distance']['text']} - {format_direction(clean_html_text(step['html_instructions']))}" for index, step in enumerate(steps)]

        directions.insert(0, f"Estimated Time of Arrival (ETA): {eta_string}\n")

        return '\n'.join(directions) + "\n\nPlease enter the building 4 and please open your Blueetooth when you are inside."
    except googlemaps.exceptions.ApiError as e:
        return f"API error: {e}"
    except googlemaps.exceptions.HTTPError as e:
        return f"HTTP error: {e}"
    except googlemaps.exceptions.Timeout:
        return "Request to Google Maps timed out."
    except googlemaps.exceptions.TransportError:
        return "There was a transport error."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

BEACON_SEQUENCE = [
    "ENTRANCE_BEACON",
    "ELEVATOR_LOBBY_BEACON",
    "THIRD_FLOOR_BEACON",
    "ROOM_HALLWAY_BEACON"
]

BEACON_INSTRUCTIONS = {
    "Entrance Beacon": "\nPlease go straight towards 50 meters. The elevator will be on your left.",
    "Elevator_Lobby Beacon": "\nTake the elevator to the 4th floor.",
    "Third_Floor Beacon": "\nTurn right, continue walking, and wait on the first left.",
    "Room_Hallway Beacon": "\nGo straight and find room 205. It will be on your right."
}

    
    #For extracting data from beacons
def get_response(beacon_status):
    for beacon, status in beacon_status.items():
        if status:
            return BEACON_INSTRUCTIONS.get(beacon, "Unknown beacon detected.")
    return "Please follow the previous instructions."



class LocationResource(resource.Resource):
    university_center = (50.130654, 8.692722)  # This is our center's coordinates
    radius = 0.150  # 150 m radius around the university

    #When we want to take GPS coordinates from client, it will come like ['lat=50.1300', 'lon=8.6800']
    #and we should read this coordinates from our server
    def _extract_query_value(self, query_list, key):
        for item in query_list:
            k, _, v = item.partition('=')
            if k == key:
                return v
        return None

    async def render_get(self, request):
      try:
        # Extract latitude, longitude and mode from the incoming request's query
        client_lat = self._extract_query_value(request.opt.uri_query, 'lat')
        client_lon = self._extract_query_value(request.opt.uri_query, 'lon')
        mode = self._extract_query_value(request.opt.uri_query, 'mode')
        building = self._extract_query_value(request.opt.uri_query, 'building')

        #For ensure that server handles all sorts of client request
        try:
            client_lat = float(client_lat)
        except (TypeError, ValueError):
            client_lat = None

        try:
            client_lon = float(client_lon)
        except (TypeError, ValueError):
            client_lon = None

        # Check coordinates are provided or not
        if client_lat is None or client_lon is None:
            return aiocoap.Message(payload="Missing coordinates".encode('utf-8'), code=aiocoap.BAD_REQUEST)
        
        #For simulating beacon's status
        if building == "True":
            beacon_status = {
                "Entrance Beacon": True,
                "Elevator_Lobby Beacon": False,
                "Third_Floor Beacon": False,
                "Room_Hallway Beacon": False,               
            }
            response = get_response(beacon_status)

        else:
               # If the client is inside the university circle
                if is_inside_or_oustide_circle(client_lat, client_lon, self.university_center[0], self.university_center[1], self.radius):        
                    response = "\n" + get_direction_from_inside(client_lat, client_lon, mode)

               # If the client is outside the university
                else:
                    response = "\n" + get_direction_to_conf(client_lat, client_lon, mode)

        return aiocoap.Message(payload=response.encode('utf-8'))
      except Exception as e:
        logging.error(f"Error while processing request: {e}")
        return aiocoap.Message(payload="Internal Server Error", code=aiocoap.INTERNAL_SERVER_ERROR)
    
class InvalidDayError(Exception):
    """Raised when an invalid day is provided."""
    pass

class AgendaResource(resource.Resource):
    def __init__(self):
        super(AgendaResource, self).__init__()
        #Agenda that shows what to do at what time
        self.monday_agenda = """
Monday, September 18
09:00am (UTC+2): Registration and Coffee

09:00am - 11:30am (UTC+2): RIOT Tutorial
(room 4-110)

11:30am - 12:30pm (UTC+2): Welcome & Keynote
(room 4-8)

12:30pm - 1:45pm (UTC+2): Lunch
(canteen)

1:45pm - 3:15pm (UTC+2): Session Networking
(room 4-8)

3:15pm - 3:45pm (UTC+2): Coffee Break
(room 4-112)

3:45pm- 5:15pm (UTC+2): Session System
(room 4-8)

5:15pm- 5:45pm (UTC+2): Planning breakout sessions
(room 4-8)

6:20pm (UTC+2): Departure for Social Event

7:00pm (UTC+2): Social Event at Zum Rad
"""
        self.tuesday_agenda = """
Tuesday, September 19
09:00am - 10:30am (UTC+2): General Assembly
(room 4-8)

10:30am - 12:30am (UTC+2): Breakout Sessions

12:30pm - 1:30am (UTC+2): Lunch
(room 4-111/112)

1:30pm- 3:00pm (UTC+2): Session Security
(room 4-8)

3:00pm - 3:30pm (UTC+2): Coffee Break
(room 4-112)

3:30pm - 5:00pm (UTC+2): Session Applications
(room 4-8)

5:00pm - 5:15pm (UTC+2): Open Mic
(room 4-8)

5:15pm - 5:30pm (UTC+2): Wrap-Up
(room 4-8)
"""




    def generate_etag(self, content):
        #We are generating ETag based on content
        return hashlib.md5(content.encode()).digest()

    def _extract_query_value(self, query_list, key):
         for item in query_list:
             k, v = item.split('=')
             if k == key:
                return v
         return None  # Make sure to return None if the key isn't found

   
    async def render_get(self, request):
     
        #We are extracting the day parameter
        day = self._extract_query_value(request.opt.uri_query, 'day')


        if not day:
            combined_agenda = self.monday_agenda + "\n" + self.tuesday_agenda
            payload = combined_agenda
        elif day == "Monday":
            payload = self.monday_agenda
        elif day == "Tuesday":
            payload = self.tuesday_agenda
        else:  # If an unrecognized day is provided
            error_message = "There is no valid day. You can only enter 'Monday', 'Tuesday' or you can let it empty."
            return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=error_message.encode('utf-8'))

        # Check for conditional GET using ETag
        current_etag = hashlib.md5(payload.encode('utf-8')).digest()  # Compute ETag for the current payload
        if 'ETag' in request.opt.option_list() and request.opt.etag == current_etag:
               response = aiocoap.Message(code=aiocoap.VALID)
        else:
               response = aiocoap.Message(payload=payload.encode('utf-8'))
        # Add ETag option to response
        response.opt.etag = current_etag
        
        response.opt.max_age = 86400  # Cache for 1 day (86400 seconds)
        return response
       #return Bad request 
async def main():
     root = resource.Site()

     root.add_resource(['.well-known', 'core'], resource.WKCResource(root.get_resources_as_linkheader))
     root.add_resource(['location'], LocationResource())
     root.add_resource(('agenda',), AgendaResource())

     await aiocoap.Context.create_server_context(bind=('::1',constants.COAP_PORT),site=root)

     await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())