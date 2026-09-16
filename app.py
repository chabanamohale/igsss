import os
from datetime import datetime

from flask import Flask, render_template

from config import config_map
from extensions import db, login_manager, bcrypt
from utils.helpers import money, humanise
from utils.security import can_access, AREA_LABELS


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "default")
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_map[config_name])

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # -- extensions ---------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # -- blueprints ---------------------------------------------------------
    from blueprints.main import main_bp
    from blueprints.auth import auth_bp
    from blueprints.citizen import citizen_bp
    from blueprints.employee import employee_bp
    from blueprints.departments import departments_bp
    from blueprints.admin import admin_bp
    from blueprints.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(citizen_bp, url_prefix="/citizen")
    app.register_blueprint(employee_bp, url_prefix="/staff")
    app.register_blueprint(departments_bp, url_prefix="/departments")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # -- template helpers ---------------------------------------------------
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["ago"] = humanise

    @app.context_processor
    def inject_globals():
        from models import Department
        return {
            "SYSTEM_NAME": app.config["SYSTEM_NAME"],
            "SYSTEM_SHORT": app.config["SYSTEM_SHORT"],
            "ORGANISATION": app.config["ORGANISATION"],
            "now": datetime.utcnow(),
            "can_access": can_access,
            "AREA_LABELS": AREA_LABELS,
            "all_departments": Department.query.order_by(Department.name).all(),
        }

    # -- error pages --------------------------------------------------------
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403,
                               heading="You are not cleared for this record",
                               detail="Your department does not hold read access to "
                                      "this area. Raise a data-sharing request if you "
                                      "need it for a case you are working on."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404,
                               heading="That page is not here",
                               detail="Check the address, or go back to your "
                                      "dashboard and start again."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/error.html", code=413,
                               heading="That file is too large",
                               detail="Uploads are limited to 8 MB. Scan documents at "
                                      "200 dpi or lower and try again."), 413

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/error.html", code=500,
                               heading="The system could not complete that request",
                               detail="The action was rolled back, so nothing was "
                                      "saved. Try again in a moment."), 500

    # -- CLI ----------------------------------------------------------------
    @app.cli.command("init-db")
    def init_db():
        """Create all tables."""
        db.create_all()
        print("Database tables created.")

    # -- ensure tables exist on startup -------------------------------------
    with app.app_context():
        db.create_all()

    return app
