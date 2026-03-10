# BedJet Alexa Smart Home Skill

Control your BedJet V3 as a native Alexa Smart Home device. Unlike the custom skill in `../alexa/`, this skill integrates directly with Alexa's device ecosystem — the BedJet appears as a thermostat in the Alexa app and responds to natural commands without an invocation name.

## Voice Commands

| Command | Example |
|---------|---------|
| Power on | "Alexa, turn on the BedJet" |
| Power off | "Alexa, turn off the BedJet" |
| Set temperature | "Alexa, set the BedJet to 80 degrees" |
| Adjust temperature | "Alexa, make the BedJet warmer" |
| Set fan speed | "Alexa, set the BedJet to 50 percent" |
| Adjust fan | "Alexa, increase the BedJet by 10 percent" |
| Set mode | "Alexa, set the BedJet mode to turbo" |
| Check status | "Alexa, what's the BedJet temperature?" |

## Capabilities

| Alexa Interface | BedJet Feature |
|----------------|----------------|
| PowerController | Turn on (defaults to heat) / off |
| ThermostatController | Set target temperature (66-109°F) |
| TemperatureSensor | Report current temperature |
| PercentageController | Fan speed (5-100%, 5% steps) |
| ModeController | heat, cool, turbo, dry, extended_heat |
| EndpointHealth | Hub/BedJet connectivity status |

## Prerequisites

- BedJet Hub server running and reachable from AWS Lambda
- [Amazon Developer](https://developer.amazon.com/) account
- AWS account with Lambda access

## Deployment

### 1. Create the Lambda function

```bash
cd lambda
zip bedjet_smarthome.zip bedjet_smarthome.py
aws lambda create-function \
  --function-name bedjet-smarthome \
  --runtime python3.12 \
  --handler bedjet_smarthome.lambda_handler \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-alexa-role \
  --zip-file fileb://bedjet_smarthome.zip \
  --timeout 15 \
  --environment "Variables={HUB_URL=http://YOUR_HUB_IP:8265}"
```

### 2. Add Alexa Smart Home trigger

```bash
aws lambda add-permission \
  --function-name bedjet-smarthome \
  --statement-id alexa-smarthome \
  --action lambda:InvokeFunction \
  --principal alexa-connectedhome.amazon.com
```

### 3. Create the Smart Home skill

In the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask):

1. Create a new skill, select **Smart Home** as the type
2. Set the **Default endpoint** to your Lambda ARN
3. Under **Account Linking** (optional):
   - If you want multi-user support, configure OAuth
   - For personal use, you can skip this
4. Save and proceed to testing

### 4. Discover the device

Say "Alexa, discover my devices" or use the Alexa app to run device discovery. The BedJet will appear as a thermostat.

### 5. Configure the Hub URL

```bash
aws lambda update-function-configuration \
  --function-name bedjet-smarthome \
  --environment "Variables={HUB_URL=http://YOUR_HUB_IP:8265}"
```

## Custom Skill vs. Smart Home Skill

| Feature | Custom Skill (`../alexa/`) | Smart Home Skill (this) |
|---------|---------------------------|------------------------|
| Invocation | "Alexa, tell bed jet to..." | "Alexa, turn on the BedJet" |
| Alexa app | Not shown as device | Appears as thermostat |
| Routines | Limited support | Full routine support |
| Timer/Presets | Supported | Not available (use custom skill) |
| Setup | Simpler | Requires device discovery |

Both skills can coexist. Use the custom skill for timer and preset commands, and the Smart Home skill for everyday control and routines.

## Updating

```bash
cd lambda
zip bedjet_smarthome.zip bedjet_smarthome.py
aws lambda update-function-code \
  --function-name bedjet-smarthome \
  --zip-file fileb://bedjet_smarthome.zip
```
