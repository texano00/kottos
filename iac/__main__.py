import time
import pulumi
import pulumi_aws as aws
from helpers.aws_organizations import AWSOrganizations
from helpers.aws_sts import AWSSTS
from components.networking import NetworkingComponent
from components.workload import WorkloadComponent

config = pulumi.Config()
aws_organizations_client = AWSOrganizations()

# Get the list of AWS accounts
aws_master_account_id = config.require('k8s_master_account_id')
aws_accounts = aws_organizations_client.list_accounts()
aws_accounts = [account for account in aws_accounts if account['Id'] != aws_master_account_id]

# Export the list of AWS accounts

pulumi.export("aws_accounts", aws_accounts)
master_aws_provider = aws.Provider("masterProvider", region="us-east-1")
master_networking = NetworkingComponent("master",
                                        "master",
                                        opts=pulumi.ResourceOptions(provider=master_aws_provider))

# generate a  public and private ssh key to be configured as user data on each ec2 instance
# add also the public key to the authorized_keys file of the ec2 instance

public_key = config.require('k8s_ssh_public_key')
private_key = config.require('k8s_ssh_private_key')


aws_sts = AWSSTS()

worker_ips = []
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
                                        (public_key, private_key),
        opts=pulumi.ResourceOptions(provider=child_provider))

    worker_ips.append(worker_workload.private_ip)

    # VPC Peering
    vpc_peering = aws.ec2.VpcPeeringConnection(f"peering-{i}",
        vpc_id=worker_networking.vpc.id,
        peer_vpc_id=master_networking.vpc.id,
        peer_owner_id=aws_master_account_id,
        opts=pulumi.ResourceOptions(provider=child_provider)
    )

    # Accept VPC Peering
    accepter = aws.ec2.VpcPeeringConnectionAccepter(f"accepter-{i}",
        vpc_peering_connection_id=vpc_peering.id,
        auto_accept=True,
        opts=pulumi.ResourceOptions(provider=master_aws_provider)
    )

    # add route to the master VPC to the existing route table of the worker VPC
    route = aws.ec2.Route(f"worker-to-master-route-{i}",
        route_table_id=worker_networking.route_table.id,
        destination_cidr_block=master_networking.vpc.cidr_block,
        vpc_peering_connection_id=vpc_peering.id,
        opts=pulumi.ResourceOptions(provider=child_provider)
    )


    # add route to the worker VPC to the existing route table of the master VPC
    route = aws.ec2.Route(f"master-to-worker-route-{i}",
        route_table_id=master_networking.route_table.id,
        destination_cidr_block=worker_networking.vpc.cidr_block,
        vpc_peering_connection_id=vpc_peering.id,
        opts=pulumi.ResourceOptions(provider=master_aws_provider)
    )


    break

time.sleep(10)
master_workload = WorkloadComponent("master",
                                    master_networking,
                                    (public_key, private_key),
                                    worker_ips,
                                    opts=pulumi.ResourceOptions(provider=master_aws_provider))


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
