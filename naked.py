import logging
import logging.config
import mysql.connector
import requests
import json
import datetime
import time
import yaml

from datetime import datetime
from configparser import ConfigParser
from mysql.connector import Error

# Loading logging configuration
with open('./log_worker.yaml', 'r') as stream:
 	log_config = yaml.safe_load(stream)

logging.config.dictConfig(log_config)

# Creating logger
logger = logging.getLogger('root')

logger.info('Asteroid processing service')

# Initiating and reading config values
logger.info('Loading configuration from file')



try:
	config = ConfigParser()
	config.read('config.ini')

	nasa_api_key = config.get('nasa', 'api_key')
	nasa_api_url = config.get('nasa', 'api_url')

	mysql_config_mysql_host = config.get('mysql_config', 'mysql_host')
	mysql_config_mysql_db = config.get('mysql_config', 'mysql_db')
	mysql_config_mysql_user = config.get('mysql_config', 'mysql_user')
	mysql_config_mysql_pass = config.get('mysql_config', 'mysql_pass')

except:
	logger.exception('')
logger.info('DONE')

def init_db():
	global connection
	connection = mysql.connector.connect(host=mysql_config_mysql_host, database=mysql_config_mysql_db, user=mysql_config_mysql_user, password=mysql_config_mysql_pass)

def get_cursor():
	global connection
	try:
		connection.ping(reconnect=True, attempts=1, delay=0)
		connection.commit()
	except mysql.connector.Error as err:
		logger.error("No connection to db " + str(err))
		connection = init_db()
		connection.commit()
	return connection.cursor()

# Check if asteroid exists in db
def mysql_check_if_ast_exists_in_db(request_day, ast_id):
	records = []
	cursor = get_cursor()
	try:
		cursor = connection.cursor()
		result  = cursor.execute("SELECT count(*) FROM ast_daily WHERE `create_date` = '" + str(request_day) + "' AND `ast_id` = '" + str(ast_id) + "'")
		records = cursor.fetchall()
		connection.commit()
	except Error as e :
		logger.error("SELECT count(*) FROM ast_daily WHERE `create_date` = '" + str(request_day) + "' AND `ast_id` = '" + str(ast_id) + "'")
		logger.error('Problem checking if asteroid exists: ' + str(e))
		pass
	return records[0][0]

# Asteroid value insert
def mysql_insert_ast_into_db(create_date, hazardous, name, url, diam_min, diam_max, ts, dt_utc, dt_local, speed, distance, ast_id):
	cursor = get_cursor()
	try:
		cursor = connection.cursor()
		result  = cursor.execute( "INSERT INTO `ast_daily` (`create_date`, `hazardous`, `name`, `url`, `diam_min`, `diam_max`, `ts`, `dt_utc`, `dt_local`, `speed`, `distance`, `ast_id`) VALUES ('" + str(create_date) + "', '" + str(hazardous) + "', '" + str(name) + "', '" + str(url) + "', '" + str(diam_min) + "', '" + str(diam_max) + "', '" + str(ts) + "', '" + str(dt_utc) + "', '" + str(dt_local) + "', '" + str(speed) + "', '" + str(distance) + "', '" + str(ast_id) + "')")
		connection.commit()
	except Error as e :
		logger.error( "INSERT INTO `ast_daily` (`create_date`, `hazardous`, `name`, `url`, `diam_min`, `diam_max`, `ts`, `dt_utc`, `dt_local`, `speed`, `distance`, `ast_id`) VALUES ('" + str(create_date) + "', '" + str(hazardous) + "', '" + str(name) + "', '" + str(url) + "', '" + str(diam_min) + "', '" + str(diam_max) + "', '" + str(ts) + "', '" + str(dt_utc) + "', '" + str(dt_local) + "', '" + str(speed) + "', '" + str(distance) + "', '" + str(ast_id) + "')")
		logger.error('Problem inserting asteroid values into DB: ' + str(e))
		pass

def push_asteroids_arrays_to_db(request_day, ast_array, hazardous):
	for asteroid in ast_array:
		if mysql_check_if_ast_exists_in_db(request_day, asteroid[9]) == 0:
			logger.debug("Asteroid NOT in db")
			mysql_insert_ast_into_db(request_day, hazardous, asteroid[0], asteroid[1], asteroid[2], asteroid[3], asteroid[4], asteroid[5], asteroid[6], asteroid[7], asteroid[8], asteroid[9])
		else:
			logger.debug("Asteroid already IN DB")

if __name__ == "__main__":

	connection = None
	connected = False

	init_db()

	# Opening connection to mysql DB
	logger.info('Connecting to MySQL DB')
	try:
		# connection = mysql.connector.connect(host=mysql_config_mysql_host, database=mysql_config_mysql_db, user=mysql_config_mysql_user, password=mysql_config_mysql_pass)
		cursor = get_cursor()
		if connection.is_connected():
			db_Info = connection.get_server_info()
			logger.info('Connected to MySQL database. MySQL Server version on ' + str(db_Info))
			cursor = connection.cursor()
			cursor.execute("select database();")
			record = cursor.fetchone()
			logger.debug('Your connected to - ' + str(record))
			connection.commit()
	except Error as e :
		logger.error('Error while connecting to MySQL' + str(e))


	# Getting todays date
	dt = datetime.now()
	request_date = str(dt.year) + "-" + str(dt.month).zfill(2) + "-" + str(dt.day).zfill(2)  
	logger.info("Generated today's date: " + str(request_date))
	
	#Requesting info from nasa
	logger.info("Request url: " + str(nasa_api_url + "rest/v1/feed?start_date=" + request_date + "&end_date=" + request_date + "&api_key=" + nasa_api_key))
	r = requests.get(nasa_api_url + "rest/v1/feed?start_date=" + request_date + "&end_date=" + request_date + "&api_key=" + nasa_api_key)
	
	# Logging response information, including status code, headers, and content
	logger.info("Response status code: " + str(r.status_code))
	logger.info("Response headers: " + str(r.headers))
	logger.info("Response content: " + str(r.text))
	
	if r.status_code == 200:
	
		json_data = json.loads(r.text)
	
		ast_safe = []
		ast_hazardous = []
	
		# Check if the 'element_count' key exists in the JSON data and log the asteroid count if found
		if 'element_count' in json_data:
			ast_count = int(json_data['element_count'])
			logger.info("Asteroid count today: " + str(ast_count))
	
			if ast_count > 0:
				for val in json_data['near_earth_objects'][request_date]:
					
					# Check if all the required keys exist in the 'val' dictionary
					if 'name' and 'nasa_jpl_url' and 'estimated_diameter' and 'is_potentially_hazardous_asteroid' and 'close_approach_data' in val:
						# If all keys exist, extract their values
						tmp_ast_name = val['name']
						tmp_ast_nasa_jpl_url = val['nasa_jpl_url']
						# Getting id of asteroid
						tmp_ast_id = val['id']
	
						# Check if 'kilometers' key exists in the 'estimated_diameter' dictionary
						if 'kilometers' in val['estimated_diameter']:
							# Check if 'estimated_diameter_min' and 'estimated_diameter_max' keys exist within 'kilometers'
							if 'estimated_diameter_min' and 'estimated_diameter_max' in val['estimated_diameter']['kilometers']:
								# Extract and round the minimum and maximum estimated diameters in kilometers
								tmp_ast_diam_min = round(val['estimated_diameter']['kilometers']['estimated_diameter_min'], 3)
								tmp_ast_diam_max = round(val['estimated_diameter']['kilometers']['estimated_diameter_max'], 3)
							else:
								# Set diameters to -2
								tmp_ast_diam_min = -2
								tmp_ast_diam_max = -2
						else:
							# Set diameters to -1
							tmp_ast_diam_min = -1
							tmp_ast_diam_max = -1
	
						tmp_ast_hazardous = val['is_potentially_hazardous_asteroid']
						
						# Check if there is close approach data available for the asteroid
						if len(val['close_approach_data']) > 0:
	
							# Check if the required keys 'epoch_date_close_approach', 'relative_velocity', and 'miss_distance' exist
							if 'epoch_date_close_approach' and 'relative_velocity' and 'miss_distance' in val['close_approach_data'][0]:
								# Extract and process the close approach timestamp
								tmp_ast_close_appr_ts = int(val['close_approach_data'][0]['epoch_date_close_approach']/1000)
								tmp_ast_close_appr_dt_utc = datetime.utcfromtimestamp(tmp_ast_close_appr_ts).strftime('%Y-%m-%d %H:%M:%S')
								tmp_ast_close_appr_dt = datetime.fromtimestamp(tmp_ast_close_appr_ts).strftime('%Y-%m-%d %H:%M:%S')
	
								
								# Check if 'kilometers_per_hour' key exists in the 'relative_velocity' dictionary of the first close approach data entry
								# If it exists, round and convert the value to an integer, otherwise, set it to -1
								if 'kilometers_per_hour' in val['close_approach_data'][0]['relative_velocity']:
									tmp_ast_speed = int(float(val['close_approach_data'][0]['relative_velocity']['kilometers_per_hour']))
								else:
									tmp_ast_speed = -1
	
								
								# Check if 'kilometers' key exists in the 'miss_distance' dictionary of the first close approach data entry
								# If it exists, round and convert the value to a floating-point number, otherwise, set it to -1
								if 'kilometers' in val['close_approach_data'][0]['miss_distance']:
									tmp_ast_miss_dist = round(float(val['close_approach_data'][0]['miss_distance']['kilometers']), 3)
								else:
									tmp_ast_miss_dist = -1
							else:
								tmp_ast_close_appr_ts = -1
								tmp_ast_close_appr_dt_utc = "1969-12-31 23:59:59"
								tmp_ast_close_appr_dt = "1969-12-31 23:59:59"
						else:
							logger.warning("No close approach data in message")
							tmp_ast_close_appr_ts = 0
							tmp_ast_close_appr_dt_utc = "1970-01-01 00:00:00"
							tmp_ast_close_appr_dt = "1970-01-01 00:00:00"
							tmp_ast_speed = -1
							tmp_ast_miss_dist = -1
	
						# Log asteroid details
						logger.info("------------------------------------------------------- >>")
						logger.info("Asteroid name: " + str(tmp_ast_name) + " | INFO: " + str(tmp_ast_nasa_jpl_url) + " | Diameter: " + str(tmp_ast_diam_min) + " - " + str(tmp_ast_diam_max) + " km | Hazardous: " + str(tmp_ast_hazardous))
						logger.info("Close approach TS: " + str(tmp_ast_close_appr_ts) + " | Date/time UTC TZ: " + str(tmp_ast_close_appr_dt_utc) + " | Local TZ: " + str(tmp_ast_close_appr_dt))
						logger.info("Speed: " + str(tmp_ast_speed) + " km/h" + " | MISS distance: " + str(tmp_ast_miss_dist) + " km")
						
						# Adding asteroid data to the corresponding array
						if tmp_ast_hazardous == True:
							ast_hazardous.append([tmp_ast_name, tmp_ast_nasa_jpl_url, tmp_ast_diam_min, tmp_ast_diam_max, tmp_ast_close_appr_ts, tmp_ast_close_appr_dt_utc, tmp_ast_close_appr_dt, tmp_ast_speed, tmp_ast_miss_dist, tmp_ast_id])
						else:
							ast_safe.append([tmp_ast_name, tmp_ast_nasa_jpl_url, tmp_ast_diam_min, tmp_ast_diam_max, tmp_ast_close_appr_ts, tmp_ast_close_appr_dt_utc, tmp_ast_close_appr_dt, tmp_ast_speed, tmp_ast_miss_dist, tmp_ast_id])
	
			else:
				logger.info("No asteroids are going to hit earth today")
				
		# Log the count of hazardous and safe asteroids as a warning
		logger.warning("Hazardous asteorids: " + str(len(ast_hazardous)) + " | Safe asteroids: " + str(len(ast_safe)))
	
		# Check if there are hazardous asteroids in the list
		if len(ast_hazardous) > 0:
			
			# Sort the hazardous asteroids by time of close approach
			ast_hazardous.sort(key = lambda x: x[4], reverse=False)
	
			# Log information about hazardous asteroids, including their close approach times and additional details
			logger.warning("Today's possible apocalypse (asteroid impact on earth) times:")
			for asteroid in ast_hazardous:
				logger.info(str(asteroid[6]) + " " + str(asteroid[0]) + " " + " | more info: " + str(asteroid[1]))
				
			# Sort the hazardous asteroids by closest passing distance
			ast_hazardous.sort(key = lambda x: x[8], reverse=False)
			
			# Log information about the hazardous asteroid with the closest passing distance
			logger.info("Closest passing distance is for: " + str(ast_hazardous[0][0]) + " at: " + str(int(ast_hazardous[0][8])) + " km | more info: " + str(ast_hazardous[0][1]))
			push_asteroids_arrays_to_db(request_date, ast_hazardous, 1)
	
		else:
			# Log a message indicating that there are no hazardous asteroids close to Earth today
			logger.info("No asteroids close passing earth today")
			
		if len(ast_safe) > 0:
			push_asteroids_arrays_to_db(request_date, ast_safe, 0)
		
	# Handle the case where there was an issue getting a response from the API
	else:
	logger.error("Unable to get response from API. Response code: " + str(r.status_code) + " | content: " + str(r.text))
