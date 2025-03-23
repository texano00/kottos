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
                               tags={"Name": f"{name}-vpc",
                                     "kubernetes.io/cluster/k0s": "owned"},
            opts=pulumi.ResourceOptions(provider=opts.provider))

        # create internet gateway and attach it to the VPC
        self.internet_gateway = aws.ec2.InternetGateway(f"{prefix}-ig",
                                                        vpc_id=self.vpc.id,
                                                        tags={"Name": f"{name}-ig"},
            opts=pulumi.ResourceOptions(provider=opts.provider))
        
        # Attach the internet gateway to the VPC
        # self.igw_attachment = aws.ec2.InternetGatewayAttachment(f"{prefix}-igw-attachment",
        #                                             vpc_id=self.vpc.id,
        #                                             internet_gateway_id=self.internet_gateway.id,
        #     opts=pulumi.ResourceOptions(provider=opts.provider))

        # Create a route table and a default route to the internet gateway
        self.route_table = aws.ec2.RouteTable(f"{prefix}-route-table",
                                              vpc_id=self.vpc.id,
                                              routes=[
                                                  {
                                                      "cidr_block": "0.0.0.0/0",
                                                      "gateway_id": self.internet_gateway.id
                                                  }
                                              ],
                                              tags={"Name": f"{name}-route-table"},
            opts=pulumi.ResourceOptions(provider=opts.provider))

        # add DefaultRouteTable
        self.default_route_table = aws.ec2.DefaultRouteTable(f"{prefix}-default-route-table",
                                                            default_route_table_id=self.route_table.id,
                                                            routes=[
                                                                {
                                                                    "cidr_block": "0.0.0.0/0",
                                                                    "gateway_id": self.internet_gateway.id
                                                                }
                                                            ],
                                                            tags={"Name": f"{name}-route-table"},
            opts=pulumi.ResourceOptions(provider=opts.provider))
        
        self.subnet_cidr = f"10.{index}.1.0/24"

        self.subnet = aws.ec2.Subnet(f"{prefix}-subnet",
                                     vpc_id=self.vpc.id,
                                     tags= {
                                         "Name": f"{name}-subnet",
                                         "kubernetes.io/role/internal-elb": "1",
                                         "kubernetes.io/cluster/k0s": "owned",
                                         "kubernetes.io/role/alb-ingress": "1",
                                         "kubernetes.io/role/elb": "1",
                                     },
                                     cidr_block=self.subnet_cidr,
                                     map_public_ip_on_launch=True,
                                     availability_zone="us-east-1a",
            opts=pulumi.ResourceOptions(provider=opts.provider))
        
        # Associate the route table with the subnet
        self.route_table_association = aws.ec2.RouteTableAssociation(f"{prefix}-route-table-association",
                                                                     subnet_id=self.subnet.id,
                                                                     route_table_id=self.route_table.id,
            opts=pulumi.ResourceOptions(provider=opts.provider))

        # MainRouteTableAssociation
        self.main_route_table_association = aws.ec2.MainRouteTableAssociation(f"{prefix}-main-route-table-association",
                                                                             vpc_id=self.vpc.id,
                                                                             route_table_id=self.route_table.id,
            opts=pulumi.ResourceOptions(provider=opts.provider))
        
        # create security group and allow all the inbound traffic from 10.0.0.0/16 if it is a worker node
        # if instead a master node, allow all the inbound traffic from 10.0.0.0/8

        # Create security group
        self.security_group = aws.ec2.SecurityGroup(f"{prefix}-sg",
                                                    vpc_id=self.vpc.id,
                                                    ingress=[
                                                        {
                                                            "protocol": "-1",
                                                            "from_port": 0,
                                                            "to_port": 0,
                                                            "cidr_blocks": ["10.0.0.0/8"]
                                                        }
                                                    ],
                                                    egress=[
                                                        {
                                                            "protocol": "-1",
                                                            "from_port": 0,
                                                            "to_port": 0,
                                                            "cidr_blocks": ["0.0.0.0/0"]
                                                        }
                                                    ],
                                                    tags={"Name": f"{name}-sg"},
            opts=pulumi.ResourceOptions(provider=opts.provider))
        self.register_outputs({
            "vpc_id": self.vpc.id,
            "subnet_id": self.subnet.id,
        })
