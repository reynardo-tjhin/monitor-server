import pathlib

from flask import Flask, Response, render_template, jsonify, request
from . import db, config, load_scripts, custom_exceptions

def create_app(module_parent_path: pathlib.Path = None, module_name: str = None) -> Flask:
    # load config - the environments (mainly Redis)
    config.load_config()

    if module_parent_path is None:
        module_parent_path = pathlib.Path(__file__).parent.parent
    
    if module_name is None:
        module_name = "scripts"
    
    # :func:`scripts_init` goes to the given directory
    # and import all the `.py` files as modules
    # then create Script object from the ID, Name, Description
    # and the execute function
    # returns the script manager object
    script_manager = load_scripts.init_script_manager(
        module_parent_path=module_parent_path,
        module_name=module_name
    )
    
    # create the app object
    app = Flask(__name__)
    
    # register database
    db.init_app(app=app)
    
    
    
    # main page
    @app.route("/")
    def index() -> str:
        """The mainpage of the web. Gets all the information of
        all the scripts and send them to the frontend.
        """
        scripts = []
        for script_id in script_manager.scripts.keys():            
            # add to the scripts list as a dictionary
            scripts.append({
                "id": script_id,
                "name": script_manager.scripts.get(script_id).name,
                "description": script_manager.scripts.get(script_id).description,
            })
        return render_template("home.html", scripts=scripts)
    
    
    
    # others page
    @app.route("/others")
    def others() -> str:
        """If there are any scripts running that send events to redis
        This page will show the events of scripts that are not added by
        the Script Manager"""
        return render_template("others.html")
    
    
    
    # for other scripts
    @app.route("/other-scripts", methods=["GET"])
    def find_other_scripts() -> Response:
        
        conn = db.get_db()
        
        # get the other scripts' id
        other_scripts_id = []
        for key in conn.keys():
            
            # built-in scripts will have "{script_id}" keys
            # other scripts that are not built-in will have
            # "others:{script_id}"
            if "others" in key.lower():
                other_scripts_id.append(key)
        
        return jsonify({
            "status": "ok",
            "message": other_scripts_id,
        })
    
    
    
    @app.route("/start-worker/<string:script_id>", methods=["POST"])
    def start_worker(script_id: str) -> Response:
        """Starting the script by creating a process using the Script manager.
        An API that returns whether the script has started successfully.
        
        :param script_id: the ID of the script.
        """
        if (request.method == "POST"):
            
            try:
                # create a process
                print(f"[INFO] Calling start_script() to start script with Script ID '{script_id}'")
                script_manager.start_script(script_id)
                print(f"[INFO] Script with Script ID '{script_id}' has started successfully")
            
            except custom_exceptions.ScriptIDError as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 400 # bad request
                
            except custom_exceptions.ScriptNotFoundError as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 404 # script not found
                
            except custom_exceptions.ScriptAlreadyRan as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 409 # conflict with its current data, version or constraints
                
            except custom_exceptions.ScriptManagerLimitExceededError as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 503 # service unavailable
            
            return jsonify({
                "status": "ok",
                "message": f"Script '{script_id}' started",
            }), 200
    
    
    
    # end worker: stop a process to end the script
    @app.route("/stop-worker/<string:script_id>", methods=["POST"])
    def stop_worker(script_id: str) -> Response:
        """Stopping the script by using :func:`terminate`.
        An API that returns whether the script has terminated successfully.
        
        :param script_id: the ID of the script.
        """
        if (request.method == "POST"):
            
            try:
                # ending a process
                print(f"[INFO] Calling end_script() to end script with Script ID '{script_id}'")
                script_manager.end_script(script_id)
                print(f"[INFO] Script with Script ID '{script_id}' has terminated successfully")
            
            except custom_exceptions.ScriptIDError as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 400 # bad request
                
            except custom_exceptions.ScriptNotFoundError as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 400 # bad request
                
            except custom_exceptions.ScriptNotRunningError as e:
                return jsonify({
                    "status": "error",
                    "message": str(e),
                }), 400 # bad request
            
            return jsonify({
                "status": "ok",
                "message": "script terminated successfully",
            }), 200
    
    
    
    # check if worker is running
    @app.route("/worker-status/<string:script_id>", methods=["GET"])
    def worker_status(script_id: str) -> Response:
        """Query the worker/script status.
        It will return the values that are returned from :func:`script_status`.
        One of the three different integer values will be returned:
        - -1: process is not alive according to :func:`process.is_alive` function
        - 0: process is still running
        - 1: process is not running
        
        :param script_id: the ID of the script.
        """
        try:
            status = script_manager.script_status(script_id)
            
        except custom_exceptions.ScriptIDError as e:
            return jsonify({
                "status": "error",
                "message": str(e),
            }), 400 # bad request
            
        except custom_exceptions.ScriptNotFoundError as e:
            return jsonify({
                "status": "error",
                "message": str(e),
                }), 400 # bad request
        
        return jsonify({
            "script_id": script_id,
            "status": status,
        }), 200
    
    
    
    @app.route("/poll/<string:script_id>", methods=["GET"])
    def poll(script_id: str) -> Response:
        """Get the latest events or messages sent from the script based on the start index.
        The messages are stored in the redis database.
        
        The key of the script is 'script:<script_id>' and the values are in the list format.
        It will require "start" query parameter. This function will return the messages from 
        the start index to the end index. 
        
        :param script_id: the ID of the script.
        """
        # get the start parameter
        start = 0
        if (request.args.get("start") is not None):
            start = int(request.args.get("start"))
            
        # get the type parameter
        type = "script" # Literal['script', 'others']
        if (request.args.get("type") is not None):
            type = request.args.get("type")
        
        # get all the messages from the start to the end
        # the messages are stored from the oldest (0th index) to the most recent ((n-1)th index)
        conn = db.get_db()
        items = conn.lrange(f"{type}:"+script_id, start=start, end=-1)

        return jsonify({
            "events": items,
            "end": start+len(items),
        }), 200
    
    return app