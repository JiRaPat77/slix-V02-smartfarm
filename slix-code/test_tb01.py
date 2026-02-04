from thingsboard import ThingsBoard
if __name__ == "__main__":
 
    tb = ThingsBoard("thingsboard.weaverbase.com", "baac@weaverbase.com", "1212312121")
    
    end = datetime.now()
    start = (end - timedelta(days=3))
    startTS = start.strftime("%Y-%m-%d %H:%M:%S")
    endTS = end.strftime("%Y-%m-%d %H:%M:%S")

    df = tb.get_data(["Humidity", "Soil Moisture_1"], startTS=startTS, endTS=endTS, device_ID="f8d52600-525d-11f0-a25a-b51fb5c43346", time='5min')
    print(df)


    # tb_mqtt = TBClientWrapper("thingsboard.weaverbase.com", token="YOUR_DEVICE_TOKEN")

  
    # tb_mqtt.send_data({"PM": 42, "temp": 30})

   
    # def handle_rpc_request(request_id, request_body):
    #     print("RPC received:", request_body)
     
    #     tb_mqtt.client.send_rpc_reply(request_id, {"status": "done"})


    # tb_mqtt.set_rpc_callback(handle_rpc_request)
    # tb_mqtt.loop_forever()


    # while True:
    #     time.sleep(1)
