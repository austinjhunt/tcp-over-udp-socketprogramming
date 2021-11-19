In this screenshot, you see a basic client<->channel<->server pipeline, where the channel is simply acting as a passthrough proxy and not dropping any messages.

On the left, the client successfully starts and finishes a three way handshake, and then immediately dives into sending messages with no problems.
No need to resend anything because all messages reach their destination, and all acknowledgements are received on the first send.

In the middle, we see the channel is simply adding small delays into the message transmissions, but is not dropping messages.

On the right, we see the server is receiving all messages from the client successfully, and is not receiving any duplicates because the client has no need to resend any messages since the channel is not lossy.
