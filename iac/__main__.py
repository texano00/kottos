import time
import pulumi
import pulumi_aws as aws
from helpers.aws_organizations import AWSOrganizations
from helpers.aws_sts import AWSSTS
from components.networking import NetworkingComponent
from components.workload import WorkloadComponent
from components.sleep import SleepComponent

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
    worker_index = i + 1
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
        worker_index,
        opts=pulumi.ResourceOptions(provider=child_provider)
    )
    worker_workload = WorkloadComponent(f"worker_{account['Id']}", worker_networking,
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

    if i == 1:
        break

sleep_component = SleepComponent("delay-before-second", delay=60)
master_workload = WorkloadComponent("master",
                                    master_networking,
                                    (public_key, private_key),
                                    worker_ips,
                                    opts=pulumi.ResourceOptions(depends_on=[sleep_component],provider=master_aws_provider))