set -e

influx -execute "CREATE DATABASE plants_measurements"
influx -execute "CREATE DATABASE analysis_data"
influx -execute "CREATE DATABASE user_notifications"