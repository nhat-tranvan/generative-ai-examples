import boto3

dynamodb = boto3.resource('dynamodb')


class TenantManagement:
    def __init__(self, tbl: str) -> None:
        self.table = dynamodb.Table(tbl)

    def get_tenant(self, tenant_id):
        response = self.table.get_item(Key={'tenantId': tenant_id})
        if response.get('Item'):
            return response['Item']
        else:
            raise Exception('Tenant NotFound')

    def is_available_token(self, tenant_id: str, spend_tokens: int):
        tenant = self.get_tenant(tenant_id)

        tenant_tokens = tenant.get('tokens', 0)

        if tenant_tokens - spend_tokens > 0:
            return True

        return False

    def spend_token(self, tenant_id: str, spend_tokens: int):
        tenant = self.get_tenant(tenant_id)

        tenant_tokens = tenant.get('tokens', 0)

        remain_tokens = tenant_tokens - spend_tokens

        if remain_tokens < 0:
            raise Exception('Invalid remain tokens')

        response = self.table.update_item(
            Key={'tenantId': tenant_id},
            UpdateExpression="set tokens=:t",
            ExpressionAttributeValues={
                ':t': remain_tokens},
            ReturnValues="UPDATED_NEW")

        return response
