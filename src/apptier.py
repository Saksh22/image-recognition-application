__copyright__   = "Copyright 2024, VISA Lab"
__license__     = "MIT"

import os
import csv
import sys
import boto3
import base64
import json
import torch
import asyncio
import subprocess
from PIL import Image
from io import BytesIO
from facenet_pytorch import MTCNN, InceptionResnetV1
from torchvision import datasets
from torch.utils.data import DataLoader



sqs = boto3.client('sqs', region_name='us-east-1', aws_access_key_id="",
aws_secret_access_key= "")
s3 = boto3.client('s3', region_name='us-east-1', aws_access_key_id="",
aws_secret_access_key= "")
ec2 = boto3.client('ec2', region_name='us-east-1', aws_access_key_id="",
aws_secret_access_key= "")
request_queue_url = 'https://sqs.us-east-1.amazonaws.com/851725184454/1229499923-req-queue'
response_queue_url = 'https://sqs.us-east-1.amazonaws.com/851725184454/1229499923-resp-queue'
input_bucket = '1229499923-in-bucket'
output_bucket = '1229499923-out-bucket'
save_directory = '/home/ubuntu/ccproject1/recieved_files'
instance_id = subprocess.check_output(['ec2-metadata', '-i']).decode('utf-8').split(': ')[-1][:-1]

mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval() # initializing resnet for face img to embeding conversion
# test_image = sys.argv[1]

def face_match(img_path, data_path): # img_path= location of photo, data_path= location of data.pt
    # getting embedding matrix of the given img
    img = Image.open(img_path)
    face, prob = mtcnn(img, return_prob=True) # returns cropped face and probability
    emb = resnet(face.unsqueeze(0)).detach() # detech is to make required gradient false

    saved_data = torch.load('data.pt') # loading data.pt file
    embedding_list = saved_data[0] # getting embedding data
    name_list = saved_data[1] # getting list of names
    dist_list = [] # list of matched distances, minimum distance is used to identify the person

    for idx, emb_db in enumerate(embedding_list):
        dist = torch.dist(emb, emb_db).item()
        dist_list.append(dist)

    idx_min = dist_list.index(min(dist_list))
    return (name_list[idx_min], min(dist_list))

async def process_images():
    flag = 0
    while True:

        messages = sqs.receive_message(
            QueueUrl=request_queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1
        )

        print("Looking for Messages")

        if 'Messages' in messages:
            flag = 0
            response = messages['Messages']

            for message in response:
                if message:
                    recepitHandle = message['ReceiptHandle']
                    body = json.loads(message['Body'])
                    print(body)
                    fileName = body['FileName']
                    s3Entry = body['S3Entry']
                    

                    s3.download_file(input_bucket, s3Entry, save_directory + "/img.jpg")
                    file_path = save_directory + "/img.jpg"
                    result = face_match(file_path, 'data.pt')
                    

                    s3.put_object(Bucket=output_bucket, Key=fileName.replace('.jpg', ''), Body=result[0])

                    body = {
                        'name': fileName,
                        'prediction': result[0]
                    }
                    response = sqs.send_message(
                        QueueUrl=response_queue_url,
                        MessageBody=(
                            json.dumps(body)
                        )
                    )
                    

                    sqs.delete_message(
                    QueueUrl=request_queue_url,
                    ReceiptHandle=recepitHandle
                )

        else:
            flag +=1

        if flag == 4:

            ec2.terminate_instances(InstanceIds=[instance_id])
            # print("Terminating this insatncce ", instance_id)
            break

        await asyncio.sleep(5)        

if __name__ == "__main__":
    # process_images()
    asyncio.get_event_loop().run_until_complete(process_images())

# result = face_match(test_image, 'data.pt')
# print(result[0])
