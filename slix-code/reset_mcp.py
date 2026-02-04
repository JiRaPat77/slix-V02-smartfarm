import time
from periphery import GPIO

mcp_1_reset = 64
mcp_2_reset = 65
mcp_3_reset = 66

Reset_MCP1 = GPIO(mcp_1_reset, "out")
Reset_MCP2 = GPIO(mcp_2_reset, "out")
Reset_MCP3 = GPIO(mcp_3_reset, "out")

Reset_MCP1.write(True) # Enable mcp23017 using convert state
Reset_MCP2.write(True) # Enable mcp23017 using convert state
Reset_MCP3.write(True) # Enable mcp23017 using convert state
time.sleep(1)
Reset_MCP1.write(False) # Enable mcp23017 using convert state
Reset_MCP2.write(False) # Enable mcp23017 using convert state
Reset_MCP3.write(False) # Enable mcp23017 using convert state
time.sleep(1)
print("Reset MCP23017 Complete")