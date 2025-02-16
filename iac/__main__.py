import pulumi
import pulumi_aws as aws


# Retrieve AWS Organization Accounts
def get_sub_accounts():
    org_accounts = aws.organizations.get_accounts()
    return [account.id for account in org_accounts.accounts if account.id != aws.organizations.get_organization().master_account_id]


sub_accounts = get_sub_accounts()

# Create VPC for Master Account
master_vpc = aws.ec2.Vpc("masterVpc",
    cidr_block="10.0.0.0/16",
)

# Create a Security Group for k0s Master Node
master_sg = aws.ec2.SecurityGroup("masterSg",
    vpc_id=master_vpc.id,
    ingress=[
        {"protocol": "tcp", "from_port": 6443, "to_port": 6443, "cidr_blocks": ["10.0.0.0/8"]},  # k8s API
    ],
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"]},
    ]
)

# Create an EC2 Instance for Master Node
master_instance = aws.ec2.Instance("masterInstance",
    ami="ami-0abcdef1234567890",  # Change to appropriate k0s AMI
    instance_type="t3.medium",
    vpc_security_group_ids=[master_sg.id],
    subnet_id=master_vpc.id,
    user_data="""#!/bin/bash
    curl -sSLf https://get.k0s.sh | sudo sh
    sudo k0s install controller --single
    sudo systemctl start k0scontroller
    """
)

# Loop through each sub-account to create VPC, peering, and worker nodes
for i, sub_account_id in enumerate(sub_accounts):
    sub_provider = aws.Provider(f"subProvider-{i}", 
        assume_role={"role_arn": f"arn:aws:iam::{sub_account_id}:role/OrganizationAccountAccessRole"},
        region="us-east-1"
    )
    
    worker_vpc = aws.ec2.Vpc(f"workerVpc-{i}",
        cidr_block=f"10.{i+1}.0.0/16",
        provider=sub_provider
    )
    
    # VPC Peering
    vpc_peering = aws.ec2.VpcPeeringConnection(f"peering-{i}",
        vpc_id=master_vpc.id,
        peer_vpc_id=worker_vpc.id,
        peer_owner_id=sub_account_id,
        provider=master_provider
    )
    
    # Worker Security Group
    worker_sg = aws.ec2.SecurityGroup(f"workerSg-{i}",
        vpc_id=worker_vpc.id,
        ingress=[
            {"protocol": "tcp", "from_port": 10250, "to_port": 10250, "cidr_blocks": ["10.0.0.0/8"]},  # Kubelet API
        ],
        provider=sub_provider
    )
    
    # Create Worker Node
    worker_instance = aws.ec2.Instance(f"workerInstance-{i}",
        ami="ami-0abcdef1234567890",
        instance_type="t3.medium",
        vpc_security_group_ids=[worker_sg.id],
        subnet_id=worker_vpc.id,
        provider=sub_provider,
        user_data=f"""#!/bin/bash
curl -sSLf https://get.k0s.sh | sudo sh
sudo k0s install worker --token-file /tmp/k0s_token
sudo systemctl start k0sworker
"""
    )
    
    pulumi.export(f"worker_instance_{i}", worker_instance.public_ip)

pulumi.export("master_instance", master_instance.public_ip)
