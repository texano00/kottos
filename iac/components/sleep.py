import pulumi
import time
from pulumi.dynamic import Resource, ResourceProvider, CreateResult


# Step 1: Create a Pulumi provider to simulate a delay
class SleepProvider(ResourceProvider):
    def create(self, props):
        delay = props.get("delay", 10)  # Default to 10 seconds
        time.sleep(delay)  # Simulate a delay
        return CreateResult("sleep-done", props)


class SleepResource(Resource):
    def __init__(self, name, delay, opts=None):
        super().__init__(SleepProvider(), name, {"delay": delay}, opts)


# Step 2: Create a ComponentResource for the delay
class SleepComponent(pulumi.ComponentResource):
    def __init__(self, name, delay, opts=None):
        super().__init__("custom:resource:SleepComponent", name, {}, opts)
        
        # The actual sleep resource
        self.sleep = SleepResource(f"{name}-sleep", delay, opts)
        
        # Register outputs
        self.register_outputs({})