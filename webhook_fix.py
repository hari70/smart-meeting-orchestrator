# Fixed webhook parsing for Surge SMS
# Replace the sms_webhook function in main.py with this:

@app.post("/webhook/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Main webhook endpoint for incoming SMS messages from Surge
    """
    try:
        # Parse incoming webhook payload
        payload = await request.json()
        logger.info(f"Received Surge SMS webhook: {payload}")
        
        # Extract SMS data from ACTUAL Surge webhook format
        event_type = payload.get("type", "")  # FIXED: was "event"
        if event_type != "message.received":
            logger.info(f"Ignoring webhook event: {event_type}")
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        # FIXED: data is in "data" not "message"
        message_data = payload.get("data", {})
        conversation_data = message_data.get("conversation", {})
        contact_data = conversation_data.get("contact", {})
        
        from_number = contact_data.get("phone_number", "").strip()
        message_text = message_data.get("body", "").strip()
        message_id = message_data.get("id", "")
        first_name = contact_data.get("first_name", "")
        last_name = contact_data.get("last_name", "")
        
        if not from_number or not message_text:
            logger.warning("Invalid Surge SMS webhook payload received")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid SMS payload"}
            )
        
        logger.info(f"Processing SMS from {from_number}: {message_text}")
        
        # Normalize phone number
        from_number = normalize_phone_number(from_number)
        
        # Process the SMS command
        response = await process_sms_command(
            from_number=from_number,
            message_text=message_text,
            first_name=first_name,
            last_name=last_name,
            db=db
        )
        
        # Send response back via SMS
        if response:
            logger.info(f"Sending response SMS to {from_number}: {response}")
            await surge_client.send_message(from_number, response, first_name, last_name)
        
        return JSONResponse(
            status_code=200,
            content={"status": "processed", "message_id": message_id}
        )
        
    except Exception as e:
        logger.error(f"Error processing Surge SMS webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )
