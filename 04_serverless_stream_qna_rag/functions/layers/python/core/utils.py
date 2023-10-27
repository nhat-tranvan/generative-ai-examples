import requests
import json
import tiktoken

URL = "https://ep928kbfdd.execute-api.us-east-1.amazonaws.com/test/"


def query_endpoint_with_json_payload(payload):
    response = requests.post(
        URL,
        json=payload,
    )
    return response


def parse_response_model_ai21(query_response):
    model_predictions = query_response.json()
    generated_text = model_predictions["answer"]
    return generated_text


def get_answer(payload):
    response = query_endpoint_with_json_payload(payload)

    generated_text = parse_response_model_ai21(response)

    return generated_text


def build_response(body, code: int):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def build_error_response(body):
    return {
        "statusCode": 402,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def text_to_tokens(text):
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))
