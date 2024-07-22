import json
import boto3
from flask import Flask, request, make_response, jsonify
import os
import base64
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from botocore.exceptions import ClientError
import threading
import time


load_dotenv()

app = Flask(__name__)

s3 = boto3.client('s3', region_name='us-east-1', aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
aws_secret_access_key= os.getenv('AWS_SECRET_ACCESS_KEY'))
sqs = boto3.client('sqs', region_name='us-east-1')
ec2 = boto3.client('ec2', aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), region_name='us-east-1')
input_bucket = 'AWS_INPUT_BUCKET'
autoscaling = boto3.client('autoscaling', region_name='us-east-1',)
launch_template_id = 'lt-09626d39302d5dfa8'

responses = {}
responses_lock = threading.Lock()
requests = 0
requests_lock = threading.Lock()

def recieve_responses():
    global requests
    global responses
    while True:
        with responses_lock:
            # Receive message from the queue
            response = sqs.receive_message(
                QueueUrl=os.getenv('RESPONSE_QUEUE_URL'),
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1
            )

            if 'Messages' in response:

                messages = response['Messages']

                for message in response['Messages']:
                    receipt_handle = message['ReceiptHandle']
                    response_body = json.loads(message['Body'])
                    # response_filename = os.path.splitext(os.path.basename(body['name']))[0]
                    resp_filename = response_body['name']
                    prediction = response_body['prediction']
                    responses[resp_filename] = prediction

                    print("Response recieved for:", resp_filename, prediction)

                    sqs.delete_message(
                            QueueUrl=os.getenv('RESPONSE_QUEUE_URL'),
                            ReceiptHandle=message['ReceiptHandle']
                    )
                    with requests_lock:
                        requests -=1
                        

        time.sleep(2)



def send_responses(filename):
    global responses
    while True:
        with responses_lock:
            if filename in responses.keys():
                result = f"{filename.split('.')[0]}:{responses[filename]}"
                print("Sending response:",result)
                del responses[filename]
                return result
        
        time.sleep(2)

def autoscale():
    """
    variable curr_instances = num

    curr_instances ++ every 5 sec until == request
    desired capacity = curr_instance

    curr_instacne > request
    desired_capacity = req

    request == 0
    curr_instance == 0
    
    
    """
    while True:
        
        messages = sqs.get_queue_attributes(
            QueueUrl=os.getenv('REQUEST_QUEUE_URL'),
            AttributeNames=['ApproximateNumberOfMessages']
        )
        number_of_messages = int(messages['Attributes']['ApproximateNumberOfMessages'])
        
        
        if number_of_messages <= 10:
            desired_instance_count = number_of_messages

        else:
            desired_instance_count = 20
              
        
        response = ec2.describe_instances(Filters=
        [{
            'Name': 'tag:Name', 'Values': ['app-tier-*']
        },
        {
            'Name': 'instance-state-name', 'Values': ['running','pending']
        }])
        running_instances_count = sum(len(reservations['Instances']) for reservations in response['Reservations'])
        
        
        if running_instances_count < desired_instance_count:
            # Launch additional instances
            instance_count = desired_instance_count - running_instances_count
            response = ec2.run_instances(
                LaunchTemplate={
                    'LaunchTemplateId': launch_template_id,
                },
                MinCount=instance_count,
                MaxCount=instance_count,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': 'app-tier-*'
                            },
                            # Add more tags if needed
                        ]
                    },
    ]
            )
            instance_ids = [instance['InstanceId'] for instance in response['Instances']]
            print(f"Launched instances: {', '.join(instance_ids)}")
            time.sleep(20)

    #     # try:
    #     with requests_lock:
    #         if requests > 10:
    #             desired_capacity = 20
    #         else:
    #             desired_capacity = requests
        

        
    #     autoscaling.update_auto_scaling_group(
    #         AutoScalingGroupName='appTierScale',  # Make sure this is your correct ASG name
    #         DesiredCapacity=desired_capacity,
    #         DefaultCooldown=5
    #     )
    # #     print(f"Autoscaling: Total instances desired is set to {desired_capacity}")
    # # except Exception as e:
    # #     print(f"Autoscaling error: {e}")  # Error handling to catch and print issues
    #     time.sleep(2)



executor = ThreadPoolExecutor(max_workers=10)
threading.Thread(target=autoscale, daemon=True).start()
threading.Thread(target=recieve_responses, daemon=True).start()



@app.route('/', methods=['POST'])
def handle_request():
    global requests
    if 'inputFile' not in request.files:
        return 'No file part', 400

    input_file = request.files['inputFile']
    filename = input_file.filename
    if filename == '':
        return 'No selected file', 400

    with requests_lock:

        requests +=1
    
    #Upload to S3 in bucket
    s3.put_object(Bucket=input_bucket, Key=filename, Body=input_file)

    body = {
        'FileName': filename,
        'S3Entry': filename,
    }

    #sending the message to sqs queue
    confirmation = sqs.send_message(
        QueueUrl=os.getenv('REQUEST_QUEUE_URL'),
        MessageBody=json.dumps(body),
    )

    print("Message sent for:", confirmation)
    
    future = executor.submit(send_responses, filename)
    result = future.result()  # Asynchronous operation
    return result, 200


if __name__ == '__main__':


    app.run(threaded=True, host="localhost", port="8000")
    
    


