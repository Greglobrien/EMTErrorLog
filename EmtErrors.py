import os
import sys
envLambdaTaskRoot = os.environ["LAMBDA_TASK_ROOT"]
#print("LAMBDA_TASK_ROOT env var:" + os.environ["LAMBDA_TASK_ROOT"])
#print("sys.path:" + str(sys.path))
sys.path.insert(0, envLambdaTaskRoot + "/requirements") ## where Libraries are
#print("sys.path:" + str(sys.path))  ## to check system Paths:

## above must come first: https://www.mandsconsulting.com/lambda-functions-with-newer-version-of-boto3-than-available-by-default/

import botocore
import boto3
import gzip
import json
import logging
import time
import re
import io

## pulled from Environment Varibales in Lambda -- default is: ERROR
log_level = os.environ['LOG_LEVEL']
log_level = log_level.upper()  ## set log level to upper case

##works with AWS Logger: https://stackoverflow.com/questions/10332748/python-logging-setlevel
logger = logging.getLogger()
level = logging.getLevelName(log_level)
logger.setLevel(level)

##log Boto & Botocore Versions, must be different for log query to work
logger.info("boto3 version:" + boto3.__version__ + "  botocore version:" + botocore.__version__)


def save_to_bucket(filename, output_to_bucket):
    ## pulled from Environment Varibales in Lambda
    aws_bucket_name = os.environ['DESTINATION_BUCKET']
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(aws_bucket_name)
    t = time.time()
    t_str = time.strftime('%m-%dT%H:%M:%S', time.gmtime(t))
    filename = filename.replace("ERROR_", "")
    path = ('%s_%s_%s_%s' % (filename, output_to_bucket['ad_adid'], output_to_bucket['ad_reid'], t_str))
    data = json.dumps(output_to_bucket, sort_keys=True, indent=4, ensure_ascii=False)

    bucket.put_object(
        ACL='private',
        ContentType='application/json',
        Key=path,
        Body=data,
    )

    body = {
        "uploaded": "true",
        "bucket": aws_bucket_name,
        "path": path,
    }

    return {
        "statusCode": 200,
        "body": json.dumps(body)
    }

def results_query(cw_logs, query_Id, eventType):
    query_result = cw_logs.get_query_results(
        queryId=query_Id
    )
    array = []
    last_adid = 1
    last_reid = 1
    error = "No error field present"
    additionalInfo = "no additional info field present"
    eventDescription = "no event Description field present"
    logger.info("Results Query - Query Result: %s " % (query_result))
    t = time.time()
    t_str = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(t))
    if (query_result['results']):
        for index, value in enumerate(query_result['results']):
            #print(index, value[1]['value'])  ## in case there is an issue, check string is present
            ## Values incoming are in quotes and must be json formatted for searching
            event = value[1]['value']
            adid = re.search('(?<=adid=)\d+', event)
            if adid:
                last_adid = adid.group(0)
            reid = re.search('(?<=reid=)\d+', event)
            if reid:
                last_reid = reid.group(0)
            formatted_json = json.loads(event)
            #print(formatted_json)
            if 'additionalInfo' in formatted_json:
                logger.debug("Results Query - Additional Info: %s" % formatted_json['additionalInfo'])
                additionalInfo = formatted_json['additionalInfo']
            if 'error' in formatted_json:
                logger.debug("Results Query - Additional Info: %s" % formatted_json['error'])
                error = formatted_json['error']
            if ((formatted_json['eventType'] == eventType) and ('eventDescription' in formatted_json)):
                logger.debug("Results Query - eventDescription: %s" % formatted_json['eventDescription'])
                eventDescription = formatted_json['eventDescription']
            array.append(formatted_json)
        queries = {"status": 200,
                   "data": array,
                   "ad_adid": last_adid,
                   "ad_reid": last_reid,
                   "ad_gmt_time": t_str,
                   "ad_error": error,
                   "ad_additionalInfo": additionalInfo,
                   "ad_eventDescription": eventDescription}
    else:
        queries = {"status": 404}
    return queries

def check_query(cw_logs, log_group, query_Id):
    current_state = ''
    finished_state = 'Complete'
    while current_state != finished_state:
        time.sleep(2)
        query_checkup = cw_logs.describe_queries(
            logGroupName=log_group
        )
        #print("query checkup: %s " % query_checkup)
        for a_query in query_checkup['queries']:
            if (a_query['queryId'] == query_Id):
                if a_query['status'] == finished_state:
                    logger.info('a_query: %s' % a_query)
                    current_state = a_query['status']
                    break

def start_insight(cw_logs, log_group, session_Id, request_Id):
    wait_time = os.environ['START_INSIGHT_PAUSE']
    time.sleep(int(wait_time)) ## wait time for execution of search
    timenow = int(time.time())
    start_time = timenow - 3600
    logger.info("timenow %s       hr_before %s" % (timenow, start_time))
    #session_Id = '3a4804e5-8c89-4d62-9807-b15df0a21984' ## -- Dev Account testing
    #request_Id = '5a3fc32a-a7ad-4feb-b0ab-442cde648d29'  ## -- Dev Account testing
    query = ("fields @timestamp, @message | sort @timestamp asc | limit 20 | filter sessionId like /(?i)(%s)/"
             " | filter requestId like /(?i)(%s)/" % (session_Id, request_Id))
    logger.info("query: %s" % query)
    ### for testing Start = 1552503526 & End = 1552507126 -- Dev Account
    response = cw_logs.start_query(
        logGroupName=log_group,
        startTime=start_time,
        endTime=timenow,
        queryString=query
    )
    logger.info("insight_response: %s\n" % response)
    return response['queryId']

def error_log_event(list_of_errors):
    for log_Event in list_of_errors:
        logger.error(log_Event)
        event_type = log_Event['eventType']
        mtConfig = log_Event['mtConfig']
        sessionId = log_Event['sessionId']
        requestId = log_Event['requestId']

        # if ('error' in ads_log.keys()):
        #     ads_error = ads_log['error']
        # else:
        #     ads_error = "No Error log Present"
        #
        # if ('adsRequestUrl' in ads_log.keys()):
        #     ads_url = ads_log['adsRequestUrl']
        # else:
        #     ads_url = "No Ads Request Url Present"

        ##Log Event data from MediaTailor to Json
        cw_logs = boto3.client('logs')
        log_group = 'MediaTailor/AdDecisionServerInteractions'
        insight_Id = start_insight(cw_logs, log_group, sessionId, requestId)
        check_query(cw_logs, log_group, insight_Id)
        cleaned_data = results_query(cw_logs, insight_Id, event_type)
        logger.info("Lambda_Handler - Cleaned Data Status: %s" % (cleaned_data['status']))

        ## Write logs out to s3, along with additional information
        if (cleaned_data['status'] == 200):
            cleaned_data['ad_event_type'] = event_type
            cleaned_data['channel_id'] = mtConfig
            # cleaned_data['ad_error'] = ads_error
            # cleaned_data['ad_request_Url'] = ads_url
            cleaned_data['ad_request_Id'] = requestId
            cleaned_data['ad_session_Id'] = sessionId
            logger.error("Status = 200 Cleaned Data: %s " % cleaned_data)
            printed_out = save_to_bucket(event_type, cleaned_data)
            logger.error(printed_out)

def split_and_search_data(substring, char_data):
    str_array = []
    string_data = char_data.split('}{')
    for idx, val in enumerate(string_data):
        logger.debug("split_and_search_data: %s %s" % (idx, val))
        if idx > 0 and idx < (len(string_data) - 1):
            new_str = "{" + val + "}"
        elif (idx == 0):
            new_str = val + "}"
        else:
            new_str = "{" + val

        if substring in new_str:
            mt_config = re.search('(?<=logStream)\W+(.\w+)', new_str)
            eventType = re.search('(?<=eventType)\W+(.\w+)', new_str)
            # https://stackoverflow.com/questions/20553051/regex-to-match-numbers-or-uuid
            requestId = re.search('(?<=requestId)\W+(\w{8}(-\w{4}){3}-\w{12}?)', new_str)
            sessionId = re.search('(?<=sessionId)\W+(\w{8}(-\w{4}){3}-\w{12}?)', new_str)
            str_dict = {"mtConfig": mt_config[1], "eventType": eventType[1], "requestId": requestId[1],
                        "sessionId": sessionId[1]}
            logger.info("split_and_search_data: %s" % str_dict)
            str_array.append(str_dict)
            # https://stackoverflow.com/questions/3895646/number-of-regex-matches
    return str_array

def download(bucket_name, input_file):
    b = io.BytesIO()
    s3_client = boto3.client('s3')
    s3_client.download_fileobj(bucket_name, input_file, b)
    ungzipped_data = gzip.decompress(b.getvalue())
    unicode_data = ungzipped_data.decode()
    return unicode_data

def check_bucket(aws_bucket_name, input_file):
    response: bool = False
    s3_resource = boto3.resource('s3')
    bucket = s3_resource.Bucket(aws_bucket_name)
    for obj in bucket.objects.all():
        key = obj.key
        if (key == input_file):
            logger.debug("true: %s" % key)
            response = True
            break
    return response

def lambda_handler(event, context):
    logger.info("event: %s \n context: %s" % (str(event), str(context)))
    aws_bucket = event['Records'][0]['s3']['bucket']['name']
    filename = event['Records'][0]['s3']['object']['key']

    if check_bucket(aws_bucket, filename):
        raw_data = download(aws_bucket, filename)
        errors_found = split_and_search_data("ERROR_", raw_data)
    else:
        errors_found = []

    if errors_found:
        error_log_event(errors_found)
    logger.info("Lambda Handler - Errors Array: %s" % errors_found)




