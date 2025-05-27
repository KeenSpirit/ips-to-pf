IPSProtectionDeviceSettings
===============

This script will transfer information from IPS to PowerFactory based on the plant number in the PF device name.

This script relies upon csv mapping files to get data from IPS into PowerFacroty.
The type_mapping.csv file is the key to all of the mapping. It associates the
relay attern in IPS to a relay type in PowerFactory and then the mapping csv that
maps each setting.

```mermaid
flowchart TD
A([main])--> B[Determine if batch update]
B-- batch --> C[Determine region]
C-- region, batch --> D[[Query IPS database]]
D--dev_list, data_capture_list --> E[[Update PowerFactory model]]
E--> F[Create save file]
F-- data_capture_list, save_file--> G[Write results to csv file]
G-- data_capture_list --> H[Print results to PF output window]
H--> I([Finish])
```