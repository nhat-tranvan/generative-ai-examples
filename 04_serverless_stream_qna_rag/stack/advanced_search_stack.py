from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_s3 as s3,
    aws_opensearchserverless as opensearchserverless,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_apigateway as apigw,
    aws_lambda_event_sources as eventsources,
    CfnParameter
)
from constructs import Construct
import os


ENV = 'aws'

class AdvancedSearchStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.IVpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        opensearch_url = CfnParameter(self, "opensearchUrl", 
                                            type="String", 
                                            default=os.environ.get('OPENSEARCH_URL'),
                                            description="The URL of opensearch serverless collection")

        opensearch_index_name = CfnParameter(self, "opensearchIndexName", 
                                            type="String", 
                                            default=os.environ.get('OPENSEARCH_INDEX_NAME'),
                                            description="The name of the opensearch index")
        
        opensearch_region = CfnParameter(self, "opensearchRegion", 
                                            type="String", 
                                            default=os.environ.get('OPENSEARCH_REGION'),
                                            description="The region of opensearch")
        
        sm_embdding_endpoint_name = CfnParameter(self, "SagemakerEmbeddingEndpointName", 
                                            type="String", 
                                            default=os.environ.get('SM_EMBEDDING_ENDPOINT_NAME'),
                                            description="Sagemaker embedding endpoint name")
        sm_embdding_endpoint_region = CfnParameter(self, "SagemakerEmbeddingEndpointRegion", 
                                            type="String", 
                                            default=os.environ.get('SM_EMBEDDING_ENDPOINT_REGION'),
                                            description="Sagemaker embedding endpoint region")
        llm_host = CfnParameter(self, "LLMHost", 
                                            type="String", 
                                            default=os.environ.get('LLM_HOST'),
                                            description="LLM Host")
        llm_port = CfnParameter(self, "LLMPort", 
                                            type="String", 
                                            default=os.environ.get('LLM_PORT'),
                                            description="LLM Port")


        datasource_bucket = s3.Bucket(self, "advanced_search_bucket",
                                      bucket_name="rag-advanced-search",
                                      block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                                      encryption=s3.BucketEncryption.S3_MANAGED,
                                      versioned=False,
                                      removal_policy=RemovalPolicy.RETAIN
                                      )

        tenant_management_table = dynamodb.Table(self, "tenant_management_table",
                                                 partition_key=dynamodb.Attribute(
                                                     name="tenantId", type=dynamodb.AttributeType.STRING)
                                                 )

        # Lambda role
        role = iam.Role(self, "Gen-AI-Lambda-Policy",
                        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaVPCAccessExecutionRole"))
        role.attach_inline_policy(iam.Policy(self, "sm-invoke-policy",
                                             statements=[iam.PolicyStatement(
                                                 effect=iam.Effect.ALLOW,
                                                 actions=[
                                                     "sagemaker:InvokeEndpoint"],
                                                 resources=["*"]
                                             )]
                                             ))
        role.attach_inline_policy(iam.Policy(self, "ddb-fullaccess",
                                             statements=[iam.PolicyStatement(
                                                 effect=iam.Effect.ALLOW,
                                                 actions=["dynamodb:*"],
                                                 resources=[
                                                     tenant_management_table.table_arn]
                                             )]
                                             ))
        role.attach_inline_policy(iam.Policy(self, "s3-fullaccess",
                                             statements=[iam.PolicyStatement(
                                                 effect=iam.Effect.ALLOW,
                                                 actions=["s3:*"],
                                                 resources=[
                                                     datasource_bucket.arn_for_objects("*")]
                                             )]
                                             ))
        role.attach_inline_policy(iam.Policy(self, "opensearchserverless-fullaccess",
                                             statements=[iam.PolicyStatement(
                                                 effect=iam.Effect.ALLOW,
                                                 actions=["aoss:*"],
                                                 resources=["*"]
                                             )]
                                             ))

        lib_layer = _lambda.LayerVersion(self, "lib",
                                         removal_policy=RemovalPolicy.RETAIN,
                                         compatible_runtimes=[
                                             _lambda.Runtime.PYTHON_3_10],
                                         code=_lambda.Code.from_asset(
                                             "functions/layers"),
                                         compatible_architectures=[
                                             _lambda.Architecture.X86_64, _lambda.Architecture.ARM_64]
                                         )

        # Amazon Lambda(Indexer)
        document_indexer_function = _lambda.Function(
            self, "document_indexer_function",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("functions/document_indexer"),
            layers=[lib_layer],
            handler="app.handler",
            role=role,
            architecture=_lambda.Architecture.X86_64,
            timeout=Duration.seconds(180),
            memory_size=512,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "TENANT_MANAGEMENT_TABLE":  tenant_management_table.table_name,
                "OPENSEARCH_URL": str(opensearch_url.value_as_string),
                "OPENSEARCH_REGION": str(opensearch_region.value_as_string),
                "OPENSEARCH_INDEX_NAME": str(opensearch_index_name.value_as_string),
                "DATASOURCE_BUCKET": datasource_bucket.bucket_name,
                "SM_ENDPOINT_NAME": sm_embdding_endpoint_name.value_as_string,
                "SM_ENDPOINT_REGION": sm_embdding_endpoint_region.value_as_string,
                "ENV": ENV
            },
            vpc=vpc
        )
        document_indexer_function.add_event_source(
            eventsources.S3EventSource(datasource_bucket,
                                       events=[s3.EventType.OBJECT_CREATED],
                                       filters=[s3.NotificationKeyFilter(
                                           prefix="documents/")]
                                       )
        )


        document_qna_function = _lambda.Function(
            self, "document_qna_function_v2",
            runtime=_lambda.Runtime.NODEJS_18_X,
            code=_lambda.Code.from_asset("functions/document_qna_stream"),
            handler="index.handler",
            role=role,
            timeout=Duration.seconds(300),
            memory_size=128,
            architecture=_lambda.Architecture.X86_64,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            environment={
                "TENANT_MANAGEMENT_TABLE":  tenant_management_table.table_name,
                "OPENSEARCH_URL": str(opensearch_url.value_as_string),
                "OPENSEARCH_REGION": str(opensearch_region.value_as_string),
                "OPENSEARCH_INDEX_NAME": str(opensearch_index_name.value_as_string),
                "DATASOURCE_BUCKET": datasource_bucket.bucket_name,
                "SM_ENDPOINT_NAME": sm_embdding_endpoint_name.value_as_string,
                "SM_ENDPOINT_REGION": sm_embdding_endpoint_region.value_as_string,
                "LLM_HOST": llm_host.value_as_string,
                "LLM_PORT": llm_port.value_as_string,
                "ENV": ENV
            },
            vpc=vpc
        )

        qna_function_url = document_qna_function.add_function_url(auth_type=_lambda.FunctionUrlAuthType.AWS_IAM, invoke_mode=_lambda.InvokeMode.RESPONSE_STREAM)

        CfnOutput(scope=self,id="QnAFunctionURL", value=qna_function_url.url)
        CfnOutput(scope=self,id="S3Bucket", value=datasource_bucket.bucket_name)

