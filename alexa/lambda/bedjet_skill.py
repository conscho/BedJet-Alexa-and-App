"""Alexa skill Lambda handler for BedJet Controller.

Forwards voice commands to the BedJet Hub server REST API.
Set the HUB_URL environment variable to your hub's address,
e.g. "http://192.168.1.50:8265".
"""

import json
import os
import logging
from urllib import request, error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HUB_URL = os.environ.get("HUB_URL", "http://bedjet-hub.local:8265")

# Valid modes and their API names
MODE_MAP = {
    "heat": "heat",
    "heating": "heat",
    "warm": "heat",
    "warm up": "heat",
    "cool": "cool",
    "cooling": "cool",
    "fan": "cool",
    "cool down": "cool",
    "turbo": "turbo",
    "turbo heat": "turbo",
    "max heat": "turbo",
    "boost": "turbo",
    "dry": "dry",
    "drying": "dry",
    "dry mode": "dry",
    "extended heat": "extended_heat",
    "ext heat": "extended_heat",
    "extended": "extended_heat",
    "long heat": "extended_heat",
}

# Friendly mode names for speech output
MODE_DISPLAY = {
    "heat": "heat",
    "cool": "cool",
    "turbo": "turbo",
    "dry": "dry",
    "extended_heat": "extended heat",
    "off": "off",
}


def hub_post(endpoint, body):
    """Send a POST request to the hub server."""
    url = f"{HUB_URL}/{endpoint}"
    data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        logger.error("Hub HTTP error %s: %s", e.code, e.read().decode())
        raise
    except error.URLError as e:
        logger.error("Hub connection error: %s", e.reason)
        raise


def hub_get(endpoint):
    """Send a GET request to the hub server."""
    url = f"{HUB_URL}/{endpoint}"
    req = request.Request(url)
    try:
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        logger.error("Hub HTTP error %s: %s", e.code, e.read().decode())
        raise
    except error.URLError as e:
        logger.error("Hub connection error: %s", e.reason)
        raise


def build_response(speech, should_end=True, card_title=None, card_text=None):
    """Build an Alexa response."""
    response = {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech,
            },
            "shouldEndSession": should_end,
        },
    }
    if card_title:
        response["response"]["card"] = {
            "type": "Simple",
            "title": card_title,
            "content": card_text or speech,
        }
    return response


def handle_set_mode(intent):
    mode_slot = intent["slots"].get("mode", {})
    spoken = (
        mode_slot.get("resolutions", {})
        .get("resolutionsPerAuthority", [{}])[0]
        .get("values", [{}])[0]
        .get("value", {})
        .get("name")
    )
    if not spoken:
        spoken = mode_slot.get("value", "").lower()

    api_mode = MODE_MAP.get(spoken)
    if not api_mode:
        return build_response(
            f"I don't recognize the mode {spoken}. "
            "You can say heat, cool, turbo, dry, or extended heat."
        )

    try:
        hub_post("mode", {"mode": api_mode})
        display = MODE_DISPLAY.get(api_mode, api_mode)
        return build_response(
            f"BedJet set to {display} mode.",
            card_title="BedJet Mode",
            card_text=f"Mode: {display}",
        )
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub. Make sure it's running."
        )


def handle_turn_off(intent):
    try:
        hub_post("mode", {"mode": "off"})
        return build_response(
            "BedJet turned off.",
            card_title="BedJet",
            card_text="Turned off",
        )
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub."
        )


def handle_set_temperature(intent):
    temp_slot = intent["slots"].get("temperature", {})
    temp_str = temp_slot.get("value")
    if not temp_str:
        return build_response("What temperature would you like? Say a number between 66 and 109.")

    try:
        temp = int(temp_str)
    except ValueError:
        return build_response("I didn't understand that temperature. Please say a number between 66 and 109.")

    if temp < 66 or temp > 109:
        return build_response(
            f"{temp} degrees is out of range. The BedJet supports 66 to 109 degrees Fahrenheit."
        )

    try:
        hub_post("temperature", {"temperature_f": temp})
        return build_response(
            f"BedJet temperature set to {temp} degrees.",
            card_title="BedJet Temperature",
            card_text=f"Target: {temp}°F",
        )
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub."
        )


def handle_set_fan(intent):
    percent_slot = intent["slots"].get("percent", {})
    percent_str = percent_slot.get("value")
    if not percent_str:
        return build_response("What fan speed? Say a percentage between 5 and 100.")

    try:
        percent = int(percent_str)
    except ValueError:
        return build_response("I didn't understand that. Please say a number between 5 and 100.")

    # Round to nearest 5%
    percent = max(5, min(100, round(percent / 5) * 5))

    try:
        hub_post("fan", {"percent": percent})
        return build_response(
            f"BedJet fan set to {percent} percent.",
            card_title="BedJet Fan",
            card_text=f"Fan: {percent}%",
        )
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub."
        )


def handle_set_preset(intent):
    preset_slot = intent["slots"].get("preset", {})
    preset_str = preset_slot.get("value")
    if not preset_str:
        return build_response("Which preset? Say 1, 2, or 3.")

    try:
        preset = int(preset_str)
    except ValueError:
        return build_response("Please say preset 1, 2, or 3.")

    if preset not in (1, 2, 3):
        return build_response("The BedJet has presets 1, 2, and 3.")

    try:
        hub_post("mode", {"mode": f"m{preset}"})
        return build_response(
            f"BedJet preset {preset} activated.",
            card_title="BedJet Preset",
            card_text=f"Preset M{preset}",
        )
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub."
        )


def handle_set_timer(intent):
    hours_slot = intent["slots"].get("hours", {})
    minutes_slot = intent["slots"].get("minutes", {})

    hours_str = hours_slot.get("value")
    minutes_str = minutes_slot.get("value")

    hours = int(hours_str) if hours_str else 0
    minutes = int(minutes_str) if minutes_str else 0

    if hours == 0 and minutes == 0:
        return build_response("How long should the BedJet run? Say a number of hours or minutes.")

    if hours > 10 or (hours == 10 and minutes > 0):
        return build_response("The maximum runtime is 10 hours.")

    try:
        hub_post("runtime", {"hours": hours, "minutes": minutes})
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        time_str = " and ".join(parts)
        return build_response(
            f"BedJet timer set to {time_str}.",
            card_title="BedJet Timer",
            card_text=f"Runtime: {time_str}",
        )
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub."
        )


def handle_get_status(intent):
    try:
        status = hub_get("status")
    except Exception:
        return build_response(
            "Sorry, I couldn't reach the BedJet hub. Make sure it's running."
        )

    if not status.get("is_connected"):
        return build_response(
            "The BedJet is not connected. Check that the hub is paired.",
            card_title="BedJet Status",
            card_text="Disconnected",
        )

    mode = status.get("mode", "Unknown")
    actual = int(status.get("actual_temp_f", 0))
    target = int(status.get("target_temp_f", 0))
    fan = status.get("fan_percent", 0)
    remaining = status.get("time_remaining", "0:00:00")

    if mode == "Standby":
        speech = f"The BedJet is off. Room temperature is {actual} degrees."
    else:
        speech = (
            f"The BedJet is in {mode} mode at {actual} degrees, "
            f"targeting {target} degrees, "
            f"fan at {fan} percent, "
            f"with {remaining} remaining."
        )

    card_text = (
        f"Mode: {mode}\n"
        f"Current: {actual}°F\n"
        f"Target: {target}°F\n"
        f"Fan: {fan}%\n"
        f"Time remaining: {remaining}"
    )

    return build_response(speech, card_title="BedJet Status", card_text=card_text)


# Intent dispatch table
INTENT_HANDLERS = {
    "SetModeIntent": handle_set_mode,
    "TurnOffIntent": handle_turn_off,
    "SetTemperatureIntent": handle_set_temperature,
    "SetFanIntent": handle_set_fan,
    "SetPresetIntent": handle_set_preset,
    "SetTimerIntent": handle_set_timer,
    "GetStatusIntent": handle_get_status,
}


def lambda_handler(event, context):
    """Main Lambda entry point for the Alexa skill."""
    logger.info("Event: %s", json.dumps(event))

    request_type = event["request"]["type"]

    if request_type == "LaunchRequest":
        return build_response(
            "BedJet controller ready. "
            "You can say things like: turn on heat, set temperature to 80 degrees, "
            "or what's the status.",
            should_end=False,
            card_title="BedJet Controller",
        )

    if request_type == "IntentRequest":
        intent = event["request"]["intent"]
        intent_name = intent["name"]

        # Built-in intents
        if intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return build_response("Goodbye.", card_title="BedJet")

        if intent_name == "AMAZON.HelpIntent":
            return build_response(
                "You can control your BedJet by saying things like: "
                "turn on heat, set temperature to 80, set fan to 50 percent, "
                "turn off, use preset 1, set timer for 3 hours, "
                "or what's the status. What would you like to do?",
                should_end=False,
                card_title="BedJet Help",
            )

        if intent_name == "AMAZON.FallbackIntent":
            return build_response(
                "I didn't understand that. Try saying: turn on heat, "
                "set temperature to 80, or what's the status.",
                should_end=False,
            )

        handler = INTENT_HANDLERS.get(intent_name)
        if handler:
            return handler(intent)

        return build_response("I'm not sure how to handle that request.")

    if request_type == "SessionEndedRequest":
        return build_response("")

    return build_response("Something went wrong.")
