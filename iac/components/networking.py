import pulumi
import pulumi_aws as aws


class NetworkingComponent(pulumi.ComponentResource):
    def __init__(self, name, type, index=None, opts=None):
        if type not in ["worker", "master"]:
            raise ValueError("type must be either 'worker' or 'master'")
        if type == "worker" and (index is None or index < 1):
            raise ValueError("positive index must be provided for worker VPCs")
        if type == "master":
            index = 0
        super().__init__('pkg:index:NetworkingComponent', name, None, opts)
        self.index = index
        prefix = f"{name}-{index}"
        self.vpc = aws.ec2.Vpc(f"{prefix}-vpc",
                               cidr_block=f"10.{index}.0.0/16",
                               enable_dns_support=True,
                               enable_dns_hostnames=True,
                               tags={"Name": f"{name}-vpc"},
            opts=pulumi.ResourceOptions(provider=opts.provider))

        self.subnet = aws.ec2.Subnet(f"{prefix}-subnet",
                                     vpc_id=self.vpc.id,
                                     cidr_block=f"10.{index}.1.0/24",
                                     map_public_ip_on_launch=True,
                                     availability_zone="us-east-1a",
            opts=pulumi.ResourceOptions(provider=opts.provider))
        # create security group and allow all the inbound traffic from 10.0.0.0/16 if it is a worker node
        # if instead a master node, allow all the inbound traffic from 10.0.0.0/8

        # Create security group
        self.security_group = aws.ec2.SecurityGroup(f"{prefix}-sg",
                                                    vpc_id=self.vpc.id,
                                                    ingress=[
                                                        {
                                                            "protocol": "tcp",
                                                            "from_port": 0,
                                                            "to_port": 65535,
                                                            "cidr_blocks": ["10.0.0.0/16"]
                                                            if type == "worker"
                                                            else ["10.0.0.0/8"]
                                                        }
                                                    ],
                                                    tags={"Name": f"{name}-sg"},
            opts=pulumi.ResourceOptions(provider=opts.provider))
        self.register_outputs({
            "vpc_id": self.vpc.id,
            "subnet_id": self.subnet.id,
        })
