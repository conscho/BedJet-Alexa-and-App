# BedJet Alexa Skill

Voice control for your BedJet V3 through the BedJet Hub server.

## Voice Commands

| Command | Example |
|---------|---------|
| Set mode | "Alexa, tell bed jet to turn on heat" |
| Turn off | "Alexa, tell bed jet to turn off" |
| Temperature | "Alexa, tell bed jet to set temperature to 80 degrees" |
| Fan speed | "Alexa, tell bed jet to set fan to 50 percent" |
| Preset | "Alexa, tell bed jet to use preset 1" |
| Timer | "Alexa, tell bed jet to set timer for 3 hours" |
| Status | "Alexa, ask bed jet for the status" |

## Prerequisites

- BedJet Hub server running and accessible from AWS Lambda
- The hub must be reachable from the internet (use a VPN, tunnel, or port forward)
- An [Amazon Developer](https://developer.amazon.com/) account
- AWS account with Lambda access

## Deployment

### 1. Create the Lambda function

```bash
cd lambda
zip bedjet_skill.zip bedjet_skill.py
aws lambda create-function \
  --function-name bedjet-controller \
  --runtime python3.12 \
  --handler bedjet_skill.lambda_handler \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-alexa-role \
  --zip-file fileb://bedjet_skill.zip \
  --timeout 15 \
  --environment "Variables={HUB_URL=http://YOUR_HUB_IP:8265}"
```

### 2. Add Alexa trigger

```bash
aws lambda add-permission \
  --function-name bedjet-controller \
  --statement-id alexa-skill \
  --action lambda:InvokeFunction \
  --principal alexa-appkit.amazon.com
```

### 3. Create the Alexa skill

Using the [ASK CLI](https://developer.amazon.com/docs/smapi/ask-cli-intro.html):

```bash
cd ..  # Back to alexa/
ask deploy
```

Or manually in the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask):

1. Create a new custom skill named "BedJet Controller"
2. Set invocation name to "bed jet"
3. Paste the contents of `interactionModels/en-US.json` into the JSON Editor
4. Set the endpoint to your Lambda function ARN
5. Build and test

### 4. Configure the Hub URL

Set the `HUB_URL` environment variable on your Lambda function to point to your hub server:

```bash
aws lambda update-function-configuration \
  --function-name bedjet-controller \
  --environment "Variables={HUB_URL=http://YOUR_HUB_IP:8265}"
```

## Network Setup

The Lambda function needs to reach your hub server. Options:

- **Tailscale/WireGuard**: Put the Lambda in a VPC with a VPN connection to your home network
- **ngrok/Cloudflare Tunnel**: Expose the hub via a tunnel and use the tunnel URL as `HUB_URL`
- **Port forwarding**: Forward port 8265 on your router (least secure)

## Updating

```bash
cd lambda
zip bedjet_skill.zip bedjet_skill.py
aws lambda update-function-code \
  --function-name bedjet-controller \
  --zip-file fileb://bedjet_skill.zip
```
