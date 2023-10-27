#!/usr/bin/env python3
import aws_cdk as cdk
from stack.advanced_search_stack import AdvancedSearchStack
from stack.vpc_stack import GenerativeAiVpcNetworkStack
import boto3
from dotenv import load_dotenv
load_dotenv()

region_name = boto3.Session().region_name
env={"region": region_name}

app = cdk.App()

network_stack = GenerativeAiVpcNetworkStack(app, "GenerativeAiVpcNetworkStack", env=env)

AdvancedSearchStack(app, "AdvancedSearchStack", vpc=network_stack.vpc, env=env)

app.synth()