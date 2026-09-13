import ast
import operator
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session as DbSession
from ..config import get_settings
from ..database import get_db
from ..models import Approval, Conversation, Memory, Message, Mission, MissionStep, Project, Session as UserSession, Task, User
from ..schemas import ApprovalDecision, CreateConversation, CreateMemory, LoginIn, MissionIn, ProjectIn, RegisterIn, SecurityTarget, TaskIn, TextIn, ToolCall
from ..security import audit, create_session, current_user, hash_password, token_hash, verify_password
from ..services.ai import AIProviderNotConfigured, AIProviderUnavailable, ChatTurn, ConversationAIService, get_ai_service

router = APIRouter()

def owned(db, model, item_id, user_id):
    item = db.get(model, item_id)
    if not item or item.user_id != user_id: raise HTTPException(404, "Resource not found")
    return item
def item(model):
    return {c.name: getattr(model, c.name) for c in model.__table__.columns}

@router.post('/auth/register', status_code=201)
def register(payload: RegisterIn, response: Response, db: DbSession = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first(): raise HTTPException(409, 'Email is already registered')
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), display_name=payload.display_name)
    db.add(user); db.commit(); db.refresh(user)
    token = create_session(db, user.id); response.set_cookie('session_token', token, httponly=True, samesite='lax', secure=get_settings().environment == 'production', max_age=get_settings().session_hours * 3600)
    audit(db, user.id, 'Registered account')
    return {'user': {'id': user.id, 'email': user.email, 'display_name': user.display_name, 'role': user.role}}

@router.post('/auth/login')
def login(payload: LoginIn, response: Response, db: DbSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash): raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid email or password')
    token = create_session(db, user.id); response.set_cookie('session_token', token, httponly=True, samesite='lax', secure=get_settings().environment == 'production', max_age=get_settings().session_hours * 3600)
    audit(db, user.id, 'Logged in')
    return {'user': {'id': user.id, 'email': user.email, 'display_name': user.display_name, 'role': user.role}}

@router.post('/auth/logout', status_code=204)
def logout(response: Response, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    db.query(UserSession).filter(UserSession.user_id == user.id).delete(); db.commit(); response.delete_cookie('session_token')
@router.get('/auth/me')
def me(user: User = Depends(current_user)): return {'id': user.id, 'email': user.email, 'display_name': user.display_name, 'role': user.role}

@router.get('/conversations')
def conversations(user: User = Depends(current_user), db: DbSession = Depends(get_db)): return [item(x) for x in db.query(Conversation).filter_by(user_id=user.id).order_by(Conversation.updated_at.desc()).all()]
@router.post('/conversations', status_code=201)
def create_conversation(payload: CreateConversation, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    value = Conversation(user_id=user.id, title=payload.title); db.add(value); db.commit(); db.refresh(value); audit(db,user.id,'Created conversation'); return item(value)
@router.get('/conversations/{conversation_id}/messages')
def messages(conversation_id: int, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    owned(db, Conversation, conversation_id, user.id); return [item(x) for x in db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at).all()]
@router.post('/conversations/{conversation_id}/messages', status_code=201)
def send_message(conversation_id: int, payload: TextIn, user: User = Depends(current_user), db: DbSession = Depends(get_db), ai: ConversationAIService = Depends(get_ai_service)):
    conversation = owned(db, Conversation, conversation_id, user.id)
    message = Message(conversation_id=conversation.id, role='user', content=payload.content.strip())
    db.add(message); db.commit(); db.refresh(message)
    history = db.query(Message).filter_by(conversation_id=conversation.id).order_by(Message.created_at.desc()).limit(get_settings().conversation_context_messages).all()
    context = [ChatTurn(role=entry.role, content=entry.content) for entry in reversed(history) if entry.role in {"user", "assistant"} and not entry.error]
    try:
        assistant = Message(conversation_id=conversation.id, role='assistant', content=ai.respond(context))
    except AIProviderNotConfigured:
        assistant = Message(conversation_id=conversation.id, role='assistant', content='ULTRON is not configured with an AI provider yet. Add the server-side provider settings, then retry this message.', error='provider_not_configured')
    except AIProviderUnavailable:
        assistant = Message(conversation_id=conversation.id, role='assistant', content='ULTRON could not reach the AI provider. Please retry shortly.', error='provider_unavailable')
    db.add(assistant); db.commit(); db.refresh(assistant)
    audit(db, user.id, 'Generated conversation response', result=assistant.error or 'completed', success=not bool(assistant.error))
    return {'user_message': item(message), 'assistant_message': item(assistant), 'streaming_ready': True}

@router.get('/memories')
def memories(q: str | None = None, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    query=db.query(Memory).filter_by(user_id=user.id)
    if q: query=query.filter(Memory.content.ilike(f'%{q}%'))
    return [item(x) for x in query.order_by(Memory.updated_at.desc()).all()]
@router.post('/memories', status_code=201)
def create_memory(payload: CreateMemory, user: User = Depends(current_user), db: DbSession = Depends(get_db)):
    value=Memory(user_id=user.id,content=payload.content,kind=payload.kind);db.add(value);db.commit();db.refresh(value);audit(db,user.id,'Stored memory');return item(value)
@router.delete('/memories/{memory_id}', status_code=204)
def delete_memory(memory_id:int,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    value=owned(db,Memory,memory_id,user.id);db.delete(value);db.commit();audit(db,user.id,'Deleted memory')

@router.get('/projects')
def projects(user:User=Depends(current_user),db:DbSession=Depends(get_db)): return [item(x) for x in db.query(Project).filter_by(user_id=user.id).all()]
@router.post('/projects',status_code=201)
def create_project(payload:ProjectIn,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    value=Project(user_id=user.id,**payload.model_dump());db.add(value);db.commit();db.refresh(value);audit(db,user.id,'Created project');return item(value)
@router.get('/tasks')
def tasks(user:User=Depends(current_user),db:DbSession=Depends(get_db)): return [item(x) for x in db.query(Task).filter_by(user_id=user.id).all()]
@router.post('/tasks',status_code=201)
def create_task(payload:TaskIn,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    if payload.project_id: owned(db,Project,payload.project_id,user.id)
    value=Task(user_id=user.id,**payload.model_dump());db.add(value);db.commit();db.refresh(value);audit(db,user.id,'Created task');return item(value)
@router.patch('/tasks/{task_id}/complete')
def complete_task(task_id:int,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    value=owned(db,Task,task_id,user.id);value.status='done';db.commit();audit(db,user.id,'Completed task');return item(value)

def plan_for(objective:str):
    return [('Clarify objective and success criteria',None,'READ_ONLY'),('Create an executable work plan','project_task_manager','SAFE_WRITE'),('Review plan and approve any external action','approval_center','EXTERNAL_ACTION'),('Verify results and produce a mission report','report_generator','READ_ONLY')]
@router.get('/missions')
def missions(user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    return [{**item(m),'steps':[item(s) for s in db.query(MissionStep).filter_by(mission_id=m.id).order_by(MissionStep.position).all()]} for m in db.query(Mission).filter_by(user_id=user.id).order_by(Mission.created_at.desc()).all()]
@router.post('/missions',status_code=201)
def create_mission(payload:MissionIn,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    mission=Mission(user_id=user.id,**payload.model_dump());db.add(mission);db.commit();db.refresh(mission)
    for position,(title,tool,permission) in enumerate(plan_for(payload.objective),1): db.add(MissionStep(mission_id=mission.id,position=position,title=title,tool_name=tool,permission_level=permission))
    approval=Approval(user_id=user.id,mission_id=mission.id,action='Approve external actions in this mission',reason='The mission may later use an external service.',risk='EXTERNAL_ACTION');db.add(approval);db.commit();audit(db,user.id,'Created mission',mission_id=mission.id);return {'mission':item(mission),'steps':[item(s) for s in db.query(MissionStep).filter_by(mission_id=mission.id).all()],'approval':item(approval)}
@router.get('/approvals')
def approvals(user:User=Depends(current_user),db:DbSession=Depends(get_db)): return [item(x) for x in db.query(Approval).filter_by(user_id=user.id).order_by(Approval.created_at.desc()).all()]
@router.post('/approvals/{approval_id}')
def decide(approval_id:int,payload:ApprovalDecision,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    approval=owned(db,Approval,approval_id,user.id);approval.status='approved' if payload.approved else 'denied';db.commit();audit(db,user.id,'Permission decision',mission_id=approval.mission_id,decision=approval.status);return item(approval)

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.USub:operator.neg}
def calculate(expression:str):
    def walk(node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:return OPS[type(node.op)](walk(node.left),walk(node.right))
        if isinstance(node,ast.UnaryOp) and type(node.op) in OPS:return OPS[type(node.op)](walk(node.operand))
        raise ValueError('Only basic numeric arithmetic is allowed')
    return walk(ast.parse(expression,mode='eval').body)
@router.get('/tools')
def tools(user:User=Depends(current_user)): return [{'name':'time','permission_level':'READ_ONLY','risk':'low'},{'name':'calculator','permission_level':'READ_ONLY','risk':'low'},{'name':'workspace_info','permission_level':'READ_ONLY','risk':'low'}]
@router.post('/tools/execute')
def tool(payload:ToolCall,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    try:
        result = datetime.now(UTC).isoformat() if payload.name=='time' else calculate(payload.expression or '') if payload.name=='calculator' else {'workspace_root':get_settings().workspace_root,'writes':'disabled without approval'}
    except (ValueError,SyntaxError,ZeroDivisionError) as exc: raise HTTPException(422,str(exc))
    audit(db,user.id,'Executed safe tool',tool=payload.name,result=str(result));return {'result':result}
@router.post('/security/analyze')
def security_analysis(payload:SecurityTarget,user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    if not payload.authorized: raise HTTPException(403,'You must confirm authorization before a security assessment.')
    audit(db,user.id,'Recorded authorized security assessment',tool='security_hygiene',result=payload.target);return {'target':payload.target,'status':'queued','scope':'Defensive hygiene only. No exploitation is performed. Configure an approved scanner adapter to run checks.'}
@router.get('/activity')
def activity(user:User=Depends(current_user),db:DbSession=Depends(get_db)):
    from ..models import Activity
    return [item(x) for x in db.query(Activity).filter_by(user_id=user.id).order_by(Activity.created_at.desc()).limit(50).all()]
