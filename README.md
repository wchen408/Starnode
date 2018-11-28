## StarNode

Weichao Chen, wchen408@gatech.edu

Grace Harper, gharper31@gatech.edu



### Design Logic

![thread_structure](thread_structure.png)



### File Descriptions

**star_node.py** : Definition of class StarNode



### Usage

#### Instantiation

Positional Argument: *node_name*, *local_port*, *max_node*

Optional arguments: *PoC_address*, *PoC_port*

Example without PoC:

```bash
python3 star_node.py node2 1222 10
```

with PoC:

```bash
python3 star_node.py node1 1111 -pa=localhost -pc=1222 10
```

#### Console Interaction

 <u>**send \[image filename] [text message]**</u>

Broadcast image file or text content through the hub

**<u>show-log</u>**

Display log of all levels

**<u>show-status</u>**

Display peer nodes, current hub, self RTTSUM

**<u>disconnect</u>**

Exit from the the network



### Assumption/Limitations

* The Starnode class relies on time.time() to determine the RTTSUM exchange time points within the network, which are defined to be every multiple of interval between two exchange time. If machines on which Starnode instances are ran don't have a consistent localtime, the RTTSUM exchange will be asynchronous and potentially not single hub will be recognized.

* Occasionally ***socket.sendto()*** throws exception despite the content being transmitted is not None

  ```
  TypeError: str, bytes or bytearray expected, not NoneType encode
  ```

* Max_node not implemented

* Python3 required
