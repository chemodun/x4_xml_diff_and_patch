# Modding tools: XML diff and patch for X4: Foundations

This tool is a simple XML diff and patch tool for X4: Foundations. It is designed to help modders to compare and patch XML files.

The format of diff XML files is compatible with the gave diff.xsd format definition. It is means - you can you this tool to create diff files for any XML files used in game.
Also you can use this tool to patch XML files with diff files, this action has reason to check how your diff file will be applied to the vanilla XML file.

## Important note
This tool is highly dependent on `diff.xsd` file. It is usually located in the `libraries` folder of the extracted game content.

The best option - to copy this file to the same folder where the tool is located. Otherwise - all tools have a `--xsd` option to specify the path to the `diff.xsd` file.


## How to use
1. Download the latest release from the [releases page](https://github.com/chemodun/x4_xml_diff_and_patch/releases/) for a platform of your choice.
    - For Windows download the:
      - `xml-diff.exe`
      - `xml-patch.exe`
    - For Linux download the:
      - `xml-diff`
      - `xml-patch`
2. You can use as a binary or as a python script.
3. Copy the files to any useful location.

### As a binary
1. Run the binary file:
    - For Windows run `xml-diff.exe` or `xml-patch.exe`.
    - For Linux run `xml-diff` or `xml-patch`.
2. Use the `--help` option to see the available commands.

### As a python script
1. Install the required dependencies using `pip install -r requirements.txt`.
2. Run the script using `python xml-diff.py` or `python xml-patch.py`.
3. Use the `--help` option to see the available commands.

### How to create a diff file
There is a command line help for the `xml-diff` tool:
```
usage: xml-diff.exe [-h] [--xsd DIFF_XSD] [original_xml] [modified_xml] [diff_xml]

Generate XML diff between two XML files or directories.

positional arguments:
  original_xml    Path to the original XML file or directory
  modified_xml    Path to the modified XML file or directory
  diff_xml        Path for the output diff XML file or directory

options:
  -h, --help      show this help message and exit
  --xsd DIFF_XSD  Path to the diff.xsd schema file
```

Example:
```
xml-diff.exe vanilla.xml modified.xml diff.xml
```
### Example of resulting diff files
There the is example of the diff files created by tool:
  - with add operation:
    ```xml
    <?xml version='1.0' encoding='UTF-8'?>
    <diff>
      <add sel="/ware[@id=&quot;satellite_mk2&quot;]" pos="after">
        <ware id="xenon_psi_emitter_mk1" name="{1972092403, 7002}" description="{1972092403, 7002}" transport="equipment" volume="1" tags="satellite noplayerbuild">
          <price min="845800" average="901420" max="1054580"/>
          <production time="60" amount="0" method="default" name="Xenon Psi Emitter"/>
          <production time="60" amount="0" method="xenon" name="Xenon Psi Emitter"/>
          <production time="60" amount="0" method="terran" name="Xenon Psi Emitter"/>
          <component ref="xenon_psi_emitter_macro" amount="0"/>
          <use threshold="0"/>
        </ware>
      </add>
    </diff>
    ```
  - with replace operation:
    ```xml
    <?xml version='1.0' encoding='UTF-8'?>
    <diff>
      <replace sel="//do_if[@value=&quot;@$speak and not this.assignedcontrolled.nextorder and (@$defaultorder.id != 'Patrol') and (@$defaultorder.id != 'ProtectPosition') and (@$defaultorder.id != 'ProtectShip') and (@$defaultorder.id != 'ProtectStation') and (@$defaultorder.id != 'Plunder') and (@$defaultorder.id != 'Police') and (not this.assignedcontrolled.commander or (this.assignedcontrolled.commander == player.occupiedship)) and notification.npc_await_orders.active&quot;]/@value">@$speak and not this.assignedcontrolled.nextorder and (@$defaultorder.id != 'ProtectSector') and (@$defaultorder.id != 'Patrol') and (@$defaultorder.id != 'ProtectPosition') and (@$defaultorder.id != 'ProtectShip') and (@$defaultorder.id != 'ProtectStation') and (@$defaultorder.id != 'Plunder') and (@$defaultorder.id != 'Police') and (not this.assignedcontrolled.commander or (this.assignedcontrolled.commander == player.occupiedship)) and notification.npc_await_orders.active</replace>
    </diff>
    ```


### How to apply a diff file
There is a command line help for the `xml-patch` tool:
```
usage: xml-patch.exe [-h] [--xsd DIFF_XSD] [original_xml] [diff_xml] [output_xml]

Apply XML diff to original XML or directory.

positional arguments:
  original_xml    Path to the original XML file or directory
  diff_xml        Path to the diff XML file or directory
  output_xml      Path for the output XML file or directory

options:
  -h, --help      show this help message and exit
  --xsd DIFF_XSD  Path to the diff.xsd schema file.
```

Example:
```
xml-patch.exe vanilla.xml diff.xml modified.xml
```

### Example of resulting patched XML files
There the is example of the patched XML files created by tool:
  - with add operation:
    ```xml
      <ware id="satellite_mk2" name="{20201,20401}" description="{20201,20402}" transport="equipment" volume="1" tags="equipment satellite">
        <price min="44380" average="52215" max="60045"/>
        <production time="60" amount="1" method="default" name="{20206,101}">
          <primary>
            <ware ware="advancedelectronics" amount="5"/>
            <ware ware="energycells" amount="10"/>
            <ware ware="scanningarrays" amount="5"/>
          </primary>
        </production>
        <production time="60" amount="1" method="xenon" name="{20206,601}" tags="noplayerbuild">
          <primary>
            <ware ware="energycells" amount="10"/>
            <ware ware="silicon" amount="1"/>
          </primary>
        </production>
        <component ref="eq_arg_satellite_02_macro"/>
        <use threshold="0"/>
      </ware>
      <ware id="xenon_psi_emitter_mk1" name="{1972092403, 7002}" description="{1972092403, 7002}" transport="equipment" volume="1" tags="satellite noplayerbuild">
        <price min="845800" average="901420" max="1054580"/>
        <production time="60" amount="0" method="default" name="Xenon Psi Emitter"/>
        <production time="60" amount="0" method="xenon" name="Xenon Psi Emitter"/>
        <production time="60" amount="0" method="terran" name="Xenon Psi Emitter"/>
        <component ref="xenon_psi_emitter_macro" amount="0"/>
        <use threshold="0"/>
      </ware>
    ```
  - with replace operation:
    ```xml
        <set_to_default_flight_control_model object="this.assignedcontrolled"/>
        <set_value name="$defaultorder" exact="this.assignedcontrolled.defaultorder"/>
        <do_if value="@$speak and not this.assignedcontrolled.nextorder and (@$defaultorder.id != 'Patrol') and (@$defaultorder.id != 'ProtectSector') and (@$defaultorder.id != 'ProtectPosition') and (@$defaultorder.id != 'ProtectShip') and (@$defaultorder.id != 'ProtectStation') and (@$defaultorder.id != 'Plunder') and (@$defaultorder.id != 'Police') and (not this.assignedcontrolled.commander or (this.assignedcontrolled.commander == player.occupiedship)) and notification.npc_await_orders.active">
          <set_value name="$speakline" exact="10304" comment="Awaiting orders."/>
    ```

### If output XML is a directory
If the output XML is a directory, the tool will create a new XML file with the same name as the original XML file in the output directory.
For example, if the original XML file is `vanilla.xml` and the output directory is `output`, the tool will create a new XML file `output/vanilla.xml`.

### How to apply a tools to a directories
You can apply the tools to directories. In this case, the tools will apply the diff or patch to all XML files in the directory.
The logic will be a next:
  - all input parameters are directories - the tools will apply the diff or patch to all XML files in the directories.
  - it will recursively gro thru the diff or changed XML files in the directories, respectively to the tool.
  - for each diff or changed files will be checked a corresponding original XML file in the original directory with the same relative path.
  - if the original XML file is not found - the diff or changed file will be skipped.
  - if the original XML file is found - the diff or changed file will be patched with the original XML file and created a new patched XML file in the output directory with the same relative path.

Example:
```
xml-diff.exe vanilla_dir modified_dir diff_dir
```
or
```
xml-patch.exe vanilla_dir diff_dir modified_dir
```
