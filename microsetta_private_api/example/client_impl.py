"""
Functions to implement OpenAPI 3.0 interface to access private PHI.

Underlies the resource server in the oauth2 workflow. "Resource Server: The
server hosting user-owned resources that are protected by OAuth2. The resource
server validates the access-token and serves the protected resources."
--https://dzone.com/articles/oauth-20-beginners-guide

Loosely based off examples in
https://realpython.com/flask-connexion-rest-api/#building-out-the-complete-api
and associated file
https://github.com/realpython/materials/blob/master/flask-connexion-rest/version_3/people.py  # noqa: E501
"""
import json
import uuid

import flask
from flask import jsonify, render_template, session, redirect
import jwt
import requests
from requests.auth import AuthBase

# Authrocket uses RS256 public keys, so you can validate anywhere and safely
# store the key in code. Obviously using this mechanism, we'd have to push code
# to roll the keys, which is not ideal, but you can instead hold this in a
# config somewhere and reload

# Python is dumb, don't put spaces anywhere in this string.
PUB_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp68T9XnX7d53Zo8pt072
y+W0sV51EDZi7f2zeBbw5qvht9coFX4LF/p9Rcac7TajVJj+YE64vHm+YAL3ToJq
XOOF/6tmPYMbbg3DRdvUopH3URCR8o7cQXN//gDKruB9+xpB3v1Wq5SCX6t8SRFw
ixw3mKgpPoh+Ou5OohxmtJ+D7lr5R2DDW8QWAWpBdGgttdnex1OqDIsprJihx/SW
sHK4ql+H4MzX5PvY7S/XF2Ibl1xWsYLPvSzV/eJoG4hIwf7efUrXiVkwqFKNYzpL
YzmOf3F/k7TdpWqzic9y0ejMKzYu0ozGlKytxp3PbpI7B18nklVkGF07g/jNPwHN
7QIDAQAB
-----END PUBLIC KEY-----"""


# Client might not technically care who the user is, but if they do, they
# get the token, validate it, and pull email out of it.
def parse_jwt(token):
    decoded = jwt.decode(token, PUB_KEY, algorithm='RS256', verify=True)
    return decoded["name"]


def rootpath():
    return redirect("/home")


def home():
    user = None
    acct_id = None
    show_wizard = False

    if 'token' in session:
        user = parse_jwt(session['token'])
        workflow_needs, workflow_state = determine_workflow_state()
        acct_id = workflow_state.get("account_id", None)
        show_wizard = workflow_needs != ALL_DONE

    # Note: home.jinja2 sends the user directly to authrocket to complete the
    # login if they aren't logged in yet.
    return render_template('home.jinja2',
                           user=user,
                           acct_id=acct_id,
                           show_wizard=show_wizard)


def authrocket_callback(token):
    session['token'] = token
    return redirect("/home")


def logout():
    del session['token']
    return redirect("/home")


# States
NEEDS_ACCOUNT = "NeedsAccount"
NEEDS_HUMAN_SOURCE = "NeedsHumanSource"
NEEDS_SAMPLE = "NeedsSample"
NEEDS_PRIMARY_SURVEY = "NeedsPrimarySurvey"
ALL_DONE = "AllDone"


def determine_workflow_state():

    # # DAN NEEDS SURVEY STUFF WOOOOOOOOO
    # current_state = {}
    # current_state["account_id"] = "44cb8726-89ae-4f2c-8966-e766fcc5d9c5"
    # current_state["human_source_id"] = "aaaaaaaa-bbbb-cccc-8966-e766fcc5d9c5"
    # return NEEDS_PRIMARY_SURVEY, current_state
    # # END STUPID.

    current_state = {}
    # Do they need to make an account? YES-> create_acct.html
    accts = ApiRequest.get("/accounts")
    if len(accts) == 0:
        return NEEDS_ACCOUNT, current_state
    acct_id = accts[0]["account_id"]
    current_state['account_id'] = acct_id

    # Do they have a human source? NO-> consent.html
    sources = ApiRequest.get("/accounts/%s/sources" % (acct_id,), params={
        "source_type": "human"
    })
    if len(sources) == 0:
        return NEEDS_HUMAN_SOURCE, current_state
    source_id = sources[0]["source_id"]
    current_state['human_source_id'] = source_id
    # Does the human source have any samples? NO-> ???.html
    # TODO fill in sample grabbing :)

    # Have you taken the primary survey? NO-> main_survey.html
    surveys = ApiRequest.get("/accounts/{0}/sources/{1}/surveys".format(
        acct_id, source_id)
    )
    has_primary = False
    for survey in surveys:
        if survey.survey_template_id == 1:
            has_primary = True
    if not has_primary:
        return NEEDS_PRIMARY_SURVEY, current_state
    # ???COVID Survey??? -> covid_survey.html
    # --> home.html
    return ALL_DONE, current_state


def workflow():
    next_state, current_state = determine_workflow_state()
    print("Next State:", next_state)
    if next_state == NEEDS_ACCOUNT:
        return redirect("/workflow_create_account")
    elif next_state == NEEDS_HUMAN_SOURCE:
        return redirect("/workflow_create_human_source_wrapper")
    elif next_state == NEEDS_PRIMARY_SURVEY:
        return redirect("/workflow_take_primary_survey")
    elif next_state == NEEDS_SAMPLE:
        pass
    elif next_state == ALL_DONE:
        return redirect("/home")


def get_workflow_create_account():
    email = parse_jwt(session['token'])
    return render_template('create_acct.jinja2',
                           authorized_email=email)


def post_workflow_create_account(body):
    kit_name = body["kit_name"]
    session['kit_name'] = kit_name

    api_json = {
        "first_name": body['first_name'],
        "last_name": body['last_name'],
        "email": body['email'],
        "address": {
            "street": body['street'],
            "city": body['city'],
            "state": body['state'],
            "post_code": body['post_code'],
            "country_code": body['country_code']
        },
        "kit_name": kit_name
    }
    resp = ApiRequest.post("/accounts", json=api_json)
    return redirect("/workflow")


def get_workflow_create_human_source_wrapper():
    return render_template('consent.jinja2')


def get_workflow_create_human_source():
    next_state, current_state = determine_workflow_state()
    acct_id = current_state["account_id"]
    post_url = "http://localhost:8082/workflow_create_human_source"
    json_of_html = ApiRequest.get("/accounts/{0}/consent".format(acct_id),
                                params={"consent_post_url": post_url})
    return json_of_html["consent_html"]


def post_workflow_create_human_source(body):
    next_state, current_state = determine_workflow_state()
    acct_id = current_state["account_id"]
    ApiRequest.post("/accounts/{0}/consent".format(acct_id), json=body)
    return redirect("/workflow")


def workflow_claim_samples():
    pass


def get_workflow_fill_primary_survey():
    next_state, current_state = determine_workflow_state()
    acct_id = current_state["account_id"]
    source_id = current_state["human_source_id"]
    primary_survey = 1
    survey_obj = ApiRequest.get('/accounts/%s/sources/%s/survey_templates/%s' %
                                (acct_id, source_id, primary_survey))
    return render_template("survey.jinja2",
                           survey_schema=survey_obj['survey_template_text'])


def post_workflow_fill_primary_survey():
    next_state, current_state = determine_workflow_state()
    acct_id = current_state["account_id"]
    source_id = current_state["human_source_id"]

    model = {}
    for x in flask.request.form:
        model[x] = flask.request.form[x]

    resp = ApiRequest.post("/accounts/%s/sources/%s/surveys" %
                           (acct_id, source_id),
                           json={
                                  "survey_template_id": 1,
                                  "survey_text": model
                                }
                           )
    return redirect("/workflow")


def workflow_assign_sample_metadata():
	# DAN
    pass


class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = "Bearer " + self.token
        return r


class ApiRequest:
    API_URL = "http://localhost:8082/api"
    DEFAULT_PARAMS = {'language_tag': 'en-US'}

    @classmethod
    def build_params(cls, params):
        all_params = {}
        for key in ApiRequest.DEFAULT_PARAMS:
            all_params[key] = ApiRequest.DEFAULT_PARAMS[key]
        if params:
            for key in params:
                all_params[key] = params[key]
        return all_params

    @classmethod
    def get(cls, path, params=None):
        return requests.get(ApiRequest.API_URL + path,
                            auth=BearerAuth(session['token']),
                            params=cls.build_params(params)).json()

    @classmethod
    def put(cls, path, params=None, json=None):
        return requests.put(ApiRequest.API_URL + path,
                            auth=BearerAuth(session['token']),
                            params=cls.build_params(params),
                            json=json).json()

    @classmethod
    def post(cls, path, params=None, json=None):
        return requests.post(ApiRequest.API_URL + path,
                             auth=BearerAuth(session['token']),
                             params=cls.build_params(params),
                             json=json).json()