from flask import jsonify

from microsetta_private_api.repo.account_repo import AccountRepo
from microsetta_private_api.repo.transaction import Transaction
from microsetta_private_api.repo.admin_repo import AdminRepo
from werkzeug.exceptions import Unauthorized


def search_barcode(token_info, sample_barcode):
    validate_admin_access(token_info)

    with Transaction() as t:
        admin_repo = AdminRepo(t)
        diag = admin_repo.retrieve_diagnostics_by_barcode(sample_barcode)
        if diag is None:
            return jsonify(code=404, message="Barcode not found"), 404
        return jsonify(diag), 200


def project_statistics_summary(token_info):
    validate_admin_access(token_info)

    with Transaction() as t:
        admin_repo = AdminRepo(t)
        summary = admin_repo.get_project_summary_statistics()
        return jsonify(summary), 200


def project_statistics_detailed(token_info, project_id):
    validate_admin_access(token_info)

    with Transaction() as t:
        admin_repo = AdminRepo(t)
        summary = admin_repo.get_project_detailed_statistics(project_id)
        return jsonify(summary), 200


def validate_admin_access(token_info):
    with Transaction() as t:
        account_repo = AccountRepo(t)
        account = account_repo.find_linked_account(token_info['iss'],
                                                   token_info['sub'])
        if account is None or account.account_type != 'admin':
            raise Unauthorized()
