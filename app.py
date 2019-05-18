#!/usr/bin/env python
import re
from collections import OrderedDict
from datetime import datetime

import pygal
import requests
from flask import (Flask, abort, jsonify, make_response, redirect,
                   render_template, request, url_for)

app = Flask(__name__)

campaigns = [
    {"name": "n1",   "country": "USA",   "budget": 149,
     "goal": "Awareness",   "category": "Technology"},
    {"name": "n2",   "country": "USA",   "budget": 149,
     "goal": "Awareness",   "category": "Sports"},
    {"name": "n3",   "country": "EGY",   "budget": 149,
     "goal": "Awareness",   "category": "Technology"},
    {"name": "n4",   "country": "USA",   "budget": 149,
     "goal": "Awareness",   "category": "Sports"},
    {"name": "n5", "country": "EGY",   "budget": 149,
     "goal": "Conversion",   "category": "Sports"}]


@app.route("/api/campaigns", methods=["POST", "GET"])
def create_campaigns():
    if request.method == "POST":
        campaign_json = request.get_json()
        if not campaign_json:
            abort(status=400)
        for key in ["name", "country", "budget", "goal"]:
            if key not in campaign_json:
                abort(status=400)
        campaign = {
            "uri": url_for(
                'update_campaign', campaign_id=len(campaigns)+1, _external=True),
            "name": campaign_json["name"],
            "country": campaign_json["country"],
            "budget": campaign_json["budget"],
            "goal": campaign_json["goal"],
            "category": campaign_json.get("category", dummy_category())
        }
        campaigns.append(campaign)

    return jsonify({"campaigns": campaigns}), 201


@app.route("/api/campaigns/<int:campaign_id>", methods=["PUT", "DELETE"])
def update_campaign(campaign_id):
    try:
        campaign = campaigns[campaign_id-1]
    except IndexError:
        abort(status=404)

    if request.method == "PUT":
        campaign_json = request.get_json()
        if not campaign_json:
            abort(status=400)
        campaign = {
            "uri": campaign["uri"],
            "name": campaign_json.get("name", campaign["name"]),
            "country": campaign_json.get("country", campaign["country"]),
            "budget": campaign_json.get("budget", campaign["budget"]),
            "goal": campaign_json.get("goal", campaign["goal"]),
            "category": campaign_json.get("category", campaign["category"])
        }
        campaigns[campaign_id-1] = campaign
    elif request.method == "DELETE":
        campaigns.pop(campaign_id-1)
    return jsonify({"campaigns": campaigns}), 201


@app.route("/api/campaigns/analysis", methods=["GET"])
def campaign_analysis():
    if not campaigns:
        abort(status=404)

    keys = [
        "name",
        "country",
        "budget",
        "goal",
        "category"]
    words = "|".join(keys)

    x, y = get_dimensions(words=words)
    fields = get_fields(words=words, keys=keys)
    start_date, end_date = get_duration()
    if end_date < start_date:
        abort(403)

    # i.e: EGY, USA
    x_axis = list(set(campaign[x] for campaign in campaigns))

    # i.e Technology : {EGY:1, USA:1}, Sports : {USA:3}
    y_axis = OrderedDict()
    for x_label in x_axis:
        for campaign in campaigns:
            if campaign[x] == x_label:
                try:
                    y_axis[campaign[y]]
                except KeyError:
                    y_axis[campaign[y]] = {campaign[x]: 1}
                    continue
                try:
                    y_axis[campaign[y]][campaign[x]] += 1
                except KeyError:
                    y_axis[campaign[y]][campaign[x]] = 1

    # Bar chart based on the given dimensions
    chart = pygal.Bar()

    chart.x_labels = x_axis

    for y_label, x_labels in y_axis.items():
        chart.add(str(y_label), [x_label for _, x_label in x_labels.items()])

    filtered_campaigns = [{key: value for key, value in campaign.items()
                           if key in fields}
                          for campaign in campaigns]

    return render_template("graph.html", graph_data=chart.render_data_uri(),
                           x=x, y=y, campaigns=filtered_campaigns,
                           start_date=start_date.date(), end_date=end_date.date())


def get_dimensions(words):
    """ returns dimensions query parameter based on given word set """
    dimensions = request.args.get(
        "dimensions", default="country,category", type=str)

    # ?dimensions format =  *** ,  ***
    dim_pattern = re.compile(
        pattern=f"^({words}),({words})$")
    dimensions = re.match(pattern=dim_pattern, string=dimensions)
    if not dimensions or dimensions[1] == dimensions[2]:
        abort(status=403)
    return dimensions[1], dimensions[2]


def get_fields(words, keys):
    """ returns fields query parameter based on given word set
    , else defaults on keys"""
    fields = request.args.get("fields", default=",".join(keys), type=str)

    # ?fields format = **, **, **... , **
    field_pattern = re.compile(
        pattern=f"^({words})(,({words}))*$")
    fields = re.match(pattern=field_pattern, string=fields)
    if not fields:
        abort(status=403)

    # removing duplicate fields
    return set(fields[0].split(","))


def get_duration():
    """ returns duration query parameter """
    duration = request.args.get(
        "duration", default="1-12-2018,1-12-2019", type=str)

    # ?duration format = dd-mm-year,dd-mm-year    start,end
    date = r"([0-2]?[0-9]|[3][0-1])-(0?[0-9]|1[0-2])-\d{4}"
    duration_pattern = re.compile(
        pattern=f"^({date}),({date})$")
    duration = re.match(pattern=duration_pattern, string=duration)
    if not duration:
        abort(status=403)
    return (datetime.strptime(date, "%d-%m-%Y")

            # first date and second date is 3 groups apart
            for date in duration.groups()[::3]
            )


def dummy_category():
    """ Returns category name from a dummy category extraction service."""
    try:
        category = requests.get(
            url=r"https://ngkc0vhbrl.execute-api.eu-west-1.amazonaws.com/api/?url=https://arabic.cnn.com/")
    except requests.RequestException:
        abort(status=501)
    else:
        return category.json()["category"]["name"]


@app.errorhandler(404)
def campaign_not_found(error):
    return make_response(jsonify({"error": "Campaign Not Found"}), 404)


@app.errorhandler(403)
def invalid_query_param(error):
    return make_response(jsonify({"error": "Invalid query parameter"}), 403)


@app.errorhandler(400)
def keys_not_filled(error):
    return make_response(jsonify({"error": "Missing required keys"}), 400)


@app.errorhandler(501)
def categry_extraction_failed(error):
    return make_response(jsonify({"error": "Couldn't extract dummy category"}), 501)


if __name__ == "__main__":
    app.run()
