import pulumi
import pulumi_aws as aws
from components.networking import NetworkingComponent


class WorkloadComponent(pulumi.ComponentResource):
    def __init__(self, name, networkingComponent: NetworkingComponent, opts=None):

        super().__init__('pkg:index:WorkloadComponent', name, None, opts)
        prefix = f"{name}-{networkingComponent.index}"
        self.instance = aws.ec2.Instance(f"{prefix}-ec2",
                                         ami="ami-053a45fff0a704a47",
                                         instance_type="t3.micro",
                                         vpc_security_group_ids=[networkingComponent.security_group.id],
                                         subnet_id=networkingComponent.subnet.id,
                                         tags={"Name": f"{name}-instance"},
            opts=pulumi.ResourceOptions(provider=opts.provider))
        self.register_outputs({
            "instance_id": self.instance.id
        })
