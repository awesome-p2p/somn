somn
====

Self-Organizing Mesh Network 

The SOMN protocol implements a two-layered network protocol for communication between distributed low-memory-footprint peers in a mesh network.  The top layer (the Communication Layer) allows a peer to send an arbitrary data stream up to a fixed length defined by the implementation.  The lower layer (the Mesh Layer) allows a peer to discover a route to any other peer in the mesh and route messages to that peer.

Requirements:
Python 3.3.3
Graphviz with dot (for viewing generated network topology graphs)

How to Use:
Execute './somnConsole.py' using Python 3.3.3
Add nodes (using 'a' menu option)
  wait for "alpha node message" after adding the first node
  Subsequent 'Add Nodes' will add node id values to the node list, enrollment messages will appear in the message window
Send messages between nodes, enter source id, destination id and message, hit return to send the message
  The message will be printed by the receiving node in the message window

To view network edges, use the 'c' option.

To generate a topology graph, use the 'p' option
  This will generate a dot graph file: graph.dot
  run './drawgraph.sh' to generate a png of the graph
  open out.png in your favorite viewer

Make massive ad-hoc network that consume all cpu cycles with glee.


Camille Huffman & Phil Lamnb
