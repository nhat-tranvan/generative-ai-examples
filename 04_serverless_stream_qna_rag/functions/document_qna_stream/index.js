import { defaultProvider } from '@aws-sdk/credential-provider-node'; // V3 SDK.
import { Client } from '@opensearch-project/opensearch';
import { AwsSigv4Signer } from '@opensearch-project/opensearch/aws';
import { SageMakerRuntimeClient, InvokeEndpointCommand } from "@aws-sdk/client-sagemaker-runtime";
import * as https from 'http';


const embeddingText = async (content) => {

    const params = {
        /** input parameters */
        EndpointName: process.env.SM_ENDPOINT_NAME,
        Body: JSON.stringify({ "text_inputs": content }),
        ContentType: "application/json"
    };

    const client = new SageMakerRuntimeClient({ region: process.env.SM_ENDPOINT_REGION });
    const command = new InvokeEndpointCommand(params);

    try {
        const response = await client.send(command)
        if (response.$metadata.httpStatusCode == 200) {
            return JSON.parse(response.Body.transformToString())['embedding'][0]
        }
        throw new Error("Cannot convert text to embedding. Check Sagemaker Endpoint")
    } catch (error) {
        // error handling.
    } finally {
        // finally.
    }
}

const similarSearch = async (vector) => {
    const client = new Client({
        ...AwsSigv4Signer({
            region: process.env.OPENSEARCH_REGION,
            service: 'aoss',
            // Example with AWS SDK V3:
            getCredentials: () => {
                // Any other method to acquire a new Credentials object can be used.
                const credentialsProvider = defaultProvider();
                return credentialsProvider();
            },
        }),
        node: process.env.OPENSEARCH_URL // OpenSearch domain URL
    });

    const query = {
        "size": 1,
        "query": {
            "knn": {
                "vector_field": {
                    "vector": vector,
                    "k": 1
                }
            }
        }
    }

    var response = await client.search({
        index: process.env.OPENSEARCH_INDEX_NAME,
        body: query,
    });

    return response;
}

export const handler = awslambda.streamifyResponse(
    async (event, responseStream, context) => {
        const httpResponseMetadata = {
            statusCode: 200,
            headers: {
                "Content-Type": "text/event-stream",
            }
        };

        responseStream = awslambda.HttpResponseStream.from(responseStream, httpResponseMetadata);

        const question = event.queryStringParameters.q || new Error('Please input your question!');

        const vector = await embeddingText(question)

        const docs = await similarSearch(vector)

        let similarContext = ''
        if (docs.body.hits.hits.length > 0) {
            similarContext = docs.body.hits.hits[0]['_source']['text']
        }

        const prompt = `<|context: ${similarContext}|>question: ${question}<|endoftext|><|assistant|>`

        const requestBody = {
            "inputs": prompt,
            "parameters": {
                "do_sample": true,
                "max_new_tokens": 200,
                "seed": 1,
                "temperature": null,
                "truncate": null,
                "typical_p": 0.2
            }
        }

        const options = {
            hostname: process.env.LLM_HOST,
            port: process.env.LLM_PORT,
            path: '/generate_stream',
            method: 'POST',
            headers: {
                'Content-type': 'application/json'
            }
        };

        let req = https.request(options, (resp) => {
            let data = '';

            resp.on('data', (chunk) => {
                data += chunk;
                responseStream.write(chunk);
            });

            resp.on('close', () => {
                console.log('Retrieved all data');
                console.log(data);
                responseStream.end();
            });
        }).on("error", (err) => {
            console.log("Error: " + err.message);
        });

        req.write(JSON.stringify(requestBody));
        req.end();
    }
);
