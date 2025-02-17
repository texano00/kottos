import boto3


class AWSClient:
    def __init__(self, service):
        self.client = boto3.client(service)

    def get_paginator(self, operation_name):
        return self.client.get_paginator(operation_name)

    def get_client(self):
        return self.client

    def list_accounts(self):
        accounts = []
        paginator = self.get_paginator("list_accounts")
        for page in paginator.paginate():
            for account in page["Accounts"]:
                accounts.append({
                    "Id": account["Id"],
                    "Name": account["Name"],
                    "Email": account["Email"],
                    "Status": account["Status"],
                })
        return accounts
