from helpers.aws import AWSClient


class AWSSTS(AWSClient):
    def __init__(self):
        super().__init__("sts")

    def assume_role(self, role_arn, role_session_name):
        assumed_role = self.client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=role_session_name
            )

        credentials = assumed_role['Credentials']
        return credentials

