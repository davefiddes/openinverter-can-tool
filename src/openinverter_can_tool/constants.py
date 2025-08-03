"""Useful constants"""

# CANopen SDO indexes used by OpenInverter systems

# Index for unique serial numbers
SERIALNO_INDEX = 0x5000

# Parameter database checksum
PARAM_DB_CHECKSUM_SUBINDEX = 3

# Index for long segmented strings
STRINGS_INDEX = 0x5001

# CANopen SDO subindex for JSON parameter databases. Used with STRINGS_INDEX
PARAM_DB_SUBINDEX = 0

# Index for sending commands - somewhat abusing the SDO protocol
COMMAND_INDEX = 0x5002

SAVE_COMMAND_SUBINDEX = 0
LOAD_COMMAND_SUBINDEX = 1
RESET_COMMAND_SUBINDEX = 2
DEFAULTS_COMMAND_SUBINDEX = 3
START_COMMAND_SUBINDEX = 4
STOP_COMMAND_SUBINDEX = 5

# CAN mapping indexes
CAN_MAP_TX_INDEX = 0x3000
CAN_MAP_RX_INDEX = 0x3001
CAN_MAP_LIST_TX_INDEX = 0x3100
CAN_MAP_LIST_RX_INDEX = 0x3180

MAP_CAN_ID_SUBINDEX = 0
MAP_PARAM_POS_LEN_SUBINDEX = 1
MAP_GAIN_OFFSET_SUBINDEX = 2

MAP_EXTENDED_FRAME_FLAG = 0x20000000
MAP_EXTENDED_FRAME_MASK = 0x1fffffff

# Start modes - tracks the _modes enum in stm32-sine
START_MODE_NORMAL = 1
START_MODE_MANUAL = 2
START_MODE_BOOST = 3
START_MODE_BUCK = 4
START_MODE_SINE = 5
START_MODE_ACHEAT = 6

# SDO abort error codes - Not defined by canopen for some reason
SDO_ABORT_OBJECT_NOT_AVAILABLE = 0x06020000
SDO_ABORT_GENERAL_FAILURE = 0x08000000

# Names for common directories
APPNAME = "openinverter_can_tool"
APPAUTHOR = "openinverter"
