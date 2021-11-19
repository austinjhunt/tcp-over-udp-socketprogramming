This is a screenshot of a JSON view of an aggregated analytics table in CouchDB.

Basically, it shows the average time to successful message acknowledgement (from the client perspective) with some different channel configurations (i.e. different drop probabilities, especially).
The docker compose environment allows you to collect this information automatically.

The client collects and writes the time measurements to CouchDB, then an independent aggregator service runs a Map Reduce algorithm on the saved documents with Apache Spark to aggregate / find averages.