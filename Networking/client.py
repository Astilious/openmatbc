import twisted.internet.reactor
import twisted.internet.protocol
import twisted.internet.defer
import twisted.spread.pb


# Minimal support code for the client connection. Parameters passed in so that
# the code can be easily adapted for more complex client functions in future if
# required.
def start_client(window, host, port):
    factory = twisted.spread.pb.PBClientFactory()
    return factory
