"""Alexa Smart Home skill Lambda handler for BedJet Controller.

Exposes the BedJet as a native Alexa Smart Home device with support for
PowerController, ThermostatController, PercentageController, and ModeController.
Communicates with the BedJet Hub server REST API.

Set the HUB_URL environment variable to your hub's address,
e.g. "http://192.168.1.50:8265".
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from urllib import error, request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HUB_URL = os.environ.get("HUB_URL", "http://bedjet-hub.local:8265")
DEVICE_ENDPOINT_ID = "bedjet-v3-01"


# --- Hub Communication ---


def hub_post(endpoint, body):
    """Send a POST request to the hub server."""
    url = f"{HUB_URL}/{endpoint}"
    data = json.dumps(body).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def hub_get(endpoint):
    """Send a GET request to the hub server."""
    url = f"{HUB_URL}/{endpoint}"
    req = request.Request(url)
    with request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- Response Helpers ---


def get_utc_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.00Z")


def make_response(namespace, name, endpoint_id=None, payload=None, context_properties=None):
    """Build a standard Alexa Smart Home response."""
    header = {
        "namespace": namespace,
        "name": name,
        "messageId": str(uuid.uuid4()),
        "payloadVersion": "3",
    }

    response = {
        "event": {
            "header": header,
            "payload": payload or {},
        }
    }

    if endpoint_id:
        response["event"]["endpoint"] = {"endpointId": endpoint_id}

    if context_properties is not None:
        response["context"] = {"properties": context_properties}

    return response


def make_error_response(error_type, message, correlation_token=None):
    """Build an Alexa error response."""
    header = {
        "namespace": "Alexa",
        "name": "ErrorResponse",
        "messageId": str(uuid.uuid4()),
        "payloadVersion": "3",
    }
    if correlation_token:
        header["correlationToken"] = correlation_token

    return {
        "event": {
            "header": header,
            "endpoint": {"endpointId": DEVICE_ENDPOINT_ID},
            "payload": {
                "type": error_type,
                "message": message,
            },
        }
    }


def get_correlation_token(directive):
    return directive.get("header", {}).get("correlationToken")


# --- Status Properties ---

# Map hub mode strings to BedJet mode values for Alexa
MODE_API_TO_ALEXA = {
    "Heat": "heat",
    "Cool": "cool",
    "Turbo": "turbo",
    "Dry": "dry",
    "Extended Heat": "extended_heat",
    "Standby": "off",
    "Wait": "off",
}

ALEXA_TO_HUB_MODE = {
    "heat": "heat",
    "cool": "cool",
    "turbo": "turbo",
    "dry": "dry",
    "extended_heat": "extended_heat",
}


def build_state_properties(status):
    """Build context properties from hub status for state reporting."""
    now = get_utc_timestamp()
    mode_str = status.get("mode", "Standby")
    alexa_mode = MODE_API_TO_ALEXA.get(mode_str, "off")
    is_on = alexa_mode != "off"

    properties = [
        {
            "namespace": "Alexa.PowerController",
            "name": "powerState",
            "value": "ON" if is_on else "OFF",
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 1000,
        },
        {
            "namespace": "Alexa.ThermostatController",
            "name": "targetSetpoint",
            "value": {
                "value": status.get("target_temp_f", 72),
                "scale": "FAHRENHEIT",
            },
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 1000,
        },
        {
            "namespace": "Alexa.TemperatureSensor",
            "name": "temperature",
            "value": {
                "value": status.get("actual_temp_f", 0),
                "scale": "FAHRENHEIT",
            },
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 1000,
        },
        {
            "namespace": "Alexa.PercentageController",
            "name": "percentage",
            "value": status.get("fan_percent", 50),
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 1000,
        },
        {
            "namespace": "Alexa.ModeController",
            "instance": "BedJet.Mode",
            "name": "mode",
            "value": alexa_mode if is_on else "heat",
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 1000,
        },
        {
            "namespace": "Alexa.EndpointHealth",
            "name": "connectivity",
            "value": {
                "value": "OK" if status.get("is_connected") else "UNREACHABLE",
            },
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 1000,
        },
    ]

    return properties


def get_status_and_properties():
    """Fetch hub status and build Alexa properties."""
    status = hub_get("status")
    return status, build_state_properties(status)


# --- Discovery ---


def handle_discovery(directive):
    """Handle Alexa.Discovery directive — report the BedJet device."""
    endpoint = {
        "endpointId": DEVICE_ENDPOINT_ID,
        "manufacturerName": "BedJet",
        "description": "BedJet V3 Climate Comfort System via Hub",
        "friendlyName": "BedJet",
        "displayCategories": ["THERMOSTAT"],
        "capabilities": [
            {
                "type": "AlexaInterface",
                "interface": "Alexa",
                "version": "3",
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.PowerController",
                "version": "3",
                "properties": {
                    "supported": [{"name": "powerState"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.ThermostatController",
                "version": "3",
                "properties": {
                    "supported": [{"name": "targetSetpoint"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                },
                "configuration": {
                    "supportedModes": ["HEAT", "COOL", "AUTO"],
                    "supportsScheduling": False,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.TemperatureSensor",
                "version": "3",
                "properties": {
                    "supported": [{"name": "temperature"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.PercentageController",
                "version": "3",
                "properties": {
                    "supported": [{"name": "percentage"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.ModeController",
                "version": "3",
                "instance": "BedJet.Mode",
                "properties": {
                    "supported": [{"name": "mode"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                    "nonControllable": False,
                },
                "capabilityResources": {
                    "friendlyNames": [
                        {
                            "value": {"text": "Mode", "locale": "en-US"},
                            "@type": "text",
                        }
                    ]
                },
                "configuration": {
                    "ordered": False,
                    "supportedModes": [
                        {
                            "value": "heat",
                            "modeResources": {
                                "friendlyNames": [
                                    {"value": {"text": "Heat", "locale": "en-US"}, "@type": "text"},
                                    {"value": {"text": "Heating", "locale": "en-US"}, "@type": "text"},
                                ]
                            },
                        },
                        {
                            "value": "cool",
                            "modeResources": {
                                "friendlyNames": [
                                    {"value": {"text": "Cool", "locale": "en-US"}, "@type": "text"},
                                    {"value": {"text": "Cooling", "locale": "en-US"}, "@type": "text"},
                                ]
                            },
                        },
                        {
                            "value": "turbo",
                            "modeResources": {
                                "friendlyNames": [
                                    {"value": {"text": "Turbo", "locale": "en-US"}, "@type": "text"},
                                    {"value": {"text": "Boost", "locale": "en-US"}, "@type": "text"},
                                ]
                            },
                        },
                        {
                            "value": "dry",
                            "modeResources": {
                                "friendlyNames": [
                                    {"value": {"text": "Dry", "locale": "en-US"}, "@type": "text"},
                                ]
                            },
                        },
                        {
                            "value": "extended_heat",
                            "modeResources": {
                                "friendlyNames": [
                                    {"value": {"text": "Extended Heat", "locale": "en-US"}, "@type": "text"},
                                    {"value": {"text": "Extended", "locale": "en-US"}, "@type": "text"},
                                ]
                            },
                        },
                    ],
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.EndpointHealth",
                "version": "3",
                "properties": {
                    "supported": [{"name": "connectivity"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                },
            },
        ],
    }

    return {
        "event": {
            "header": {
                "namespace": "Alexa.Discovery",
                "name": "Discover.Response",
                "messageId": str(uuid.uuid4()),
                "payloadVersion": "3",
            },
            "payload": {
                "endpoints": [endpoint],
            },
        }
    }


# --- Directive Handlers ---


def handle_power_turn_on(directive):
    """Handle Alexa.PowerController TurnOn."""
    token = get_correlation_token(directive)
    try:
        # Default to heat mode when turning on
        hub_post("mode", {"mode": "heat"})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("TurnOn failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_power_turn_off(directive):
    """Handle Alexa.PowerController TurnOff."""
    token = get_correlation_token(directive)
    try:
        hub_post("mode", {"mode": "off"})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("TurnOff failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_set_target_temperature(directive):
    """Handle Alexa.ThermostatController SetTargetTemperature."""
    token = get_correlation_token(directive)
    try:
        temp_value = directive["payload"]["targetSetpoint"]["value"]
        scale = directive["payload"]["targetSetpoint"].get("scale", "FAHRENHEIT")

        if scale == "CELSIUS":
            temp_f = temp_value * 9.0 / 5.0 + 32.0
        else:
            temp_f = temp_value

        temp_f = max(66, min(109, round(temp_f)))

        hub_post("temperature", {"temperature_f": temp_f})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("SetTargetTemperature failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_adjust_target_temperature(directive):
    """Handle Alexa.ThermostatController AdjustTargetTemperature."""
    token = get_correlation_token(directive)
    try:
        delta = directive["payload"]["targetSetpointDelta"]["value"]
        scale = directive["payload"]["targetSetpointDelta"].get("scale", "FAHRENHEIT")

        if scale == "CELSIUS":
            delta_f = delta * 9.0 / 5.0
        else:
            delta_f = delta

        status = hub_get("status")
        current = status.get("target_temp_f", 72)
        new_temp = max(66, min(109, round(current + delta_f)))

        hub_post("temperature", {"temperature_f": new_temp})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("AdjustTargetTemperature failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_set_percentage(directive):
    """Handle Alexa.PercentageController SetPercentage."""
    token = get_correlation_token(directive)
    try:
        percent = int(directive["payload"]["percentage"])
        # Round to nearest 5% (BedJet uses 5% steps)
        percent = max(5, min(100, round(percent / 5) * 5))

        hub_post("fan", {"percent": percent})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("SetPercentage failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_adjust_percentage(directive):
    """Handle Alexa.PercentageController AdjustPercentage."""
    token = get_correlation_token(directive)
    try:
        delta = int(directive["payload"]["percentageDelta"])

        status = hub_get("status")
        current = status.get("fan_percent", 50)
        new_percent = max(5, min(100, round((current + delta) / 5) * 5))

        hub_post("fan", {"percent": new_percent})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("AdjustPercentage failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_set_mode(directive):
    """Handle Alexa.ModeController SetMode."""
    token = get_correlation_token(directive)
    try:
        alexa_mode = directive["payload"]["mode"]
        hub_mode = ALEXA_TO_HUB_MODE.get(alexa_mode)

        if not hub_mode:
            return make_error_response(
                "INVALID_VALUE",
                f"Unknown mode: {alexa_mode}",
                token,
            )

        hub_post("mode", {"mode": hub_mode})
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "Response", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("SetMode failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


def handle_report_state(directive):
    """Handle Alexa ReportState — return current device state."""
    token = get_correlation_token(directive)
    try:
        _, props = get_status_and_properties()
        resp = make_response("Alexa", "StateReport", DEVICE_ENDPOINT_ID, context_properties=props)
        resp["event"]["header"]["correlationToken"] = token
        return resp
    except Exception as e:
        logger.error("ReportState failed: %s", e)
        return make_error_response("ENDPOINT_UNREACHABLE", str(e), token)


# --- Directive Dispatch ---

DIRECTIVE_HANDLERS = {
    ("Alexa.Discovery", "Discover"): handle_discovery,
    ("Alexa.PowerController", "TurnOn"): handle_power_turn_on,
    ("Alexa.PowerController", "TurnOff"): handle_power_turn_off,
    ("Alexa.ThermostatController", "SetTargetTemperature"): handle_set_target_temperature,
    ("Alexa.ThermostatController", "AdjustTargetTemperature"): handle_adjust_target_temperature,
    ("Alexa.PercentageController", "SetPercentage"): handle_set_percentage,
    ("Alexa.PercentageController", "AdjustPercentage"): handle_adjust_percentage,
    ("Alexa.ModeController", "SetMode"): handle_set_mode,
    ("Alexa", "ReportState"): handle_report_state,
}


def lambda_handler(event, context):
    """Main Lambda entry point for the Alexa Smart Home skill."""
    logger.info("Event: %s", json.dumps(event))

    directive = event.get("directive", {})
    header = directive.get("header", {})
    namespace = header.get("namespace", "")
    name = header.get("name", "")

    handler = DIRECTIVE_HANDLERS.get((namespace, name))
    if handler:
        try:
            return handler(directive)
        except error.URLError as e:
            logger.error("Hub connection error: %s", e)
            return make_error_response(
                "ENDPOINT_UNREACHABLE",
                "Cannot reach BedJet hub. Ensure it is running.",
                get_correlation_token(directive),
            )
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return make_error_response(
                "INTERNAL_ERROR",
                str(e),
                get_correlation_token(directive),
            )

    logger.warning("Unhandled directive: %s %s", namespace, name)
    return make_error_response(
        "INVALID_DIRECTIVE",
        f"Unsupported directive: {namespace}.{name}",
        get_correlation_token(directive),
    )
