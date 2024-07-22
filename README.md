# Image Recognition Application

## Overview
This project involves setting up an image recognition system using AWS services. The system consists of a Web Tier to receive image inputs from users, forward them to the App Tier for inference, and return the recognition results. The App Tier performs the actual image recognition using a deep learning model and is designed to scale automatically based on request demand. The Data Tier stores images and results in S3 buckets for persistence.

## Components
1. Web Tier
2. App Tier
3. Data Tier

## Web Tier
The Web Tier in this project is an AWS EC2 instance hosting a Flask application. It handles HTTP POST requests containing images and performs the following functions:

1. Forwarding Images: Receives images from users via HTTP POST requests and forwards them to the SQS request queue for processing.
2. Receiving Results: Retrieves recognition results from the SQS response queue and sends them back to the users.
3. Autoscaling: Monitors the request load and dynamically adjusts the number of instances in the App Tier to ensure optimal performance and resource utilization.

## App Tier
The App Tier in this project consists of AWS EC2 instances hosting a ResNet model. It performs the following operations:

1. Image Recognition: Receives images from the SQS request queue and performs image recognition using the ResNet model.
2. Sending Results: Sends the recognition results to the SQS response queue.
3. Data Persistence: Stores the recognition results in the Data Tier for persistence and future reference.

## Data Tier
The Data Tier consists of AWS S3 buckets which stores the input images and corresponding recognition results in key-value pairs.
