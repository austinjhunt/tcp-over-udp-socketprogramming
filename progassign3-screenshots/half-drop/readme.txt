In this screenshot, you can see the client on the left tries to send a message chunk "rying to sen" but times out waiting for an ACK from the server, so keeps resending because it assumes the message is undelivered.
Since the drop rate for both client messages and server ACKs is 50%, we get a string of failed acknowledgements here and the client ends up resending that one message chunk 7 more times.

In the middle, you can see that the channel drops multiple messages from the client and drops multiple ACKS from the server, which reflects the 50% drop rate in both directions.

On the right, you can see the server is receiving the "rying to sen" chunk multiple times, but because of the sequence number, it recognizes the message as a duplicate.

Eventually, the client finally receives an ACK of the "rying to sen" message chunk, finally satisfying the "stop-and-wait" condition and moving on to the next chunk, "d a message".