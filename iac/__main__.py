import pulumi
import pulumi_aws as aws
from helpers.aws_organizations import AWSOrganizations
from helpers.aws_sts import AWSSTS
from components.networking import NetworkingComponent
from components.workload import WorkloadComponent

aws_organizations_client = AWSOrganizations()

# Get the list of AWS accounts
aws_accounts = aws_organizations_client.list_accounts()
aws_accounts = [account for account in aws_accounts if account['Id'] != pulumi.Config().get("k8s_master.account_id")]

# Export the list of AWS accounts
pulumi.export("aws_accounts", aws_accounts)
master_aws_provider = aws.Provider("masterProvider", region="us-east-1")
master_networking = NetworkingComponent("master",
                                        "master",
                                        opts=pulumi.ResourceOptions(provider=master_aws_provider))

master_workload = WorkloadComponent("master",
                                    master_networking,
                                    opts=pulumi.ResourceOptions(provider=master_aws_provider))
aws_sts = AWSSTS()

for i, account in enumerate(aws_accounts):

    credentials = aws_sts.assume_role(f"arn:aws:iam::{account['Id']}:role/ChildAccountRole",
                                      'PulumiSession')

    child_provider = aws.Provider(f"subProvider-{account['Id']}",
        access_key=credentials['AccessKeyId'],
        secret_key=credentials['SecretAccessKey'],
        token=credentials['SessionToken'],
        region="us-east-1"
    )

    worker_networking = NetworkingComponent(f"worker_{account['Id']}",
        "worker",
        1,
        opts=pulumi.ResourceOptions(provider=child_provider)
    )

    worker_workload = WorkloadComponent("worker", worker_networking,
        opts=pulumi.ResourceOptions(provider=child_provider))
    
    break

#     # VPC Peering
#     vpc_peering = aws.ec2.VpcPeeringConnection(f"peering-{i}",
#         vpc_id=master_vpc.id,
#         peer_vpc_id=worker_vpc.id,
#         peer_owner_id=sub_account_id,
#         provider=master_provider
#     )
    
#     # Worker Security Group
#     worker_sg = aws.ec2.SecurityGroup(f"workerSg-{i}",
#         vpc_id=worker_vpc.id,
#         ingress=[
#             {"protocol": "tcp", "from_port": 10250, "to_port": 10250, "cidr_blocks": ["10.0.0.0/8"]},  # Kubelet API
#         ],
#         provider=sub_provider
#     )
    
#     # Create Worker Node
#     worker_instance = aws.ec2.Instance(f"workerInstance-{i}",
#         ami="ami-0abcdef1234567890",
#         instance_type="t3.medium",
#         vpc_security_group_ids=[worker_sg.id],
#         subnet_id=worker_vpc.id,
#         provider=sub_provider,
#         user_data=f"""#!/bin/bash
# curl -sSLf https://get.k0s.sh | sudo sh
# sudo k0s install worker --token-file /tmp/k0s_token
# sudo systemctl start k0sworker
# """
#     )
    
#     pulumi.export(f"worker_instance_{i}", worker_instance.public_ip)

# pulumi.export("master_instance", master_instance.public_ip)
