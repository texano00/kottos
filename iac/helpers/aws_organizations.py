from helpers.aws import AWSClient


class AWSOrganizations(AWSClient):
    def __init__(self):
        super().__init__("organizations")

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
