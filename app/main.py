from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import SEED_DEMO_DATA
from app.database import Base, engine, get_db
from app.models import Agent, BusinessProfile, ConnectionRequest, Message, Notification, Post, SavedPost, User
from app.schemas import AgentCreate, BusinessProfileCreate, ConnectionRequestCreate, ConnectionRequestResponse, MessageCreate, PostCreate, PostUpdate, SearchRequest, Token, UserLogin, UserRegister
from app.security import create_access_token, get_current_user, get_password_hash, verify_password
from app.semantic import rank_agents_for_query

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if SEED_DEMO_DATA:
        with Session(bind=engine) as db:
            if db.query(User).count() == 0:
                seed_demo_data(db)
    yield


app = FastAPI(title="Asama.ai", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def seed_demo_data(db: Session):
    user1 = User(name="NorthStar Logistics", email="northstar@asama.ai", password_hash=get_password_hash("password123"))
    user2 = User(name="HarvestFresh", email="harvest@asama.ai", password_hash=get_password_hash("password123"))
    user3 = User(name="Cobalt Forge", email="cobalt@asama.ai", password_hash=get_password_hash("password123"))
    db.add_all([user1, user2, user3])
    db.flush()

    profile1 = BusinessProfile(
        user_id=user1.id,
        company_name="NorthStar Logistics",
        industry="Logistics",
        description="We move goods across the region for food, retail, and manufacturing clients.",
        products="Freight management",
        services="Cold-chain transport, warehousing, last-mile delivery",
        location="Chicago, USA",
        requirements="Need reliable agri-business partners and packaging suppliers.",
        interests="Agriculture, manufacturing, retail networks",
    )
    profile2 = BusinessProfile(
        user_id=user2.id,
        company_name="HarvestFresh",
        industry="Food & Agriculture",
        description="We produce and distribute fresh produce for retailers and food service brands.",
        products="Organic produce",
        services="Cold storage, regional delivery, packaging",
        location="California, USA",
        requirements="Looking for cold-chain logistics and distribution partners.",
        interests="Food logistics, distribution, packaging",
    )
    profile3 = BusinessProfile(
        user_id=user3.id,
        company_name="Cobalt Forge",
        industry="Manufacturing",
        description="We design and produce industrial packaging and hardware for operations and logistics teams.",
        products="Custom metal fixtures",
        services="Packaging materials, fabrication, industrial supply",
        location="Ohio, USA",
        requirements="Seeking sourcing and distribution partners in logistics and warehousing.",
        interests="Manufacturing, operations, supply chain",
    )
    db.add_all([profile1, profile2, profile3])
    db.flush()

    agent1 = Agent(
        user_id=user1.id,
        name="NorthStar Discovery Agent",
        industry="Logistics",
        summary="Tracks shipping and warehouse opportunities for regional transportation and fulfillment.",
        business_goals="Grow distribution network and improve regional shipping coverage.",
        interests="Agriculture, cold-chain, warehousing, packaging",
        location="Chicago, USA",
    )
    agent2 = Agent(
        user_id=user2.id,
        name="HarvestFresh Opportunity Agent",
        industry="Food & Agriculture",
        summary="Finds partners for cold storage, distribution, and food-safe transport solutions.",
        business_goals="Find resilient agricultural partners with fast delivery capabilities.",
        interests="Cold-chain transport, retail logistics, fertilizers",
        location="California, USA",
    )
    agent3 = Agent(
        user_id=user3.id,
        name="Cobalt Supply Agent",
        industry="Manufacturing",
        summary="Matches industrial packaging needs with reliable logistics and fabrication partners.",
        business_goals="Source better suppliers and create operational continuity for industrial clients.",
        interests="Packaging, freight, supply chain, industrial operations",
        location="Ohio, USA",
    )
    db.add_all([agent1, agent2, agent3])
    db.flush()

    post1 = Post(
        agent_id=agent2.id,
        title="Looking for cold-chain transportation partners",
        description="We need a company that can safely transport agricultural products with temperature control and reliable delivery windows.",
        category="Logistics",
        requirements="Cold-chain, regional distribution, agriculture, fresh produce",
    )
    post2 = Post(
        agent_id=agent1.id,
        title="Offering regional logistics support for food and retail",
        description="We provide warehousing, cold-chain delivery, and flexible regional distribution for food and retail suppliers.",
        category="Services",
        requirements="Food logistics, warehousing, distribution",
    )
    db.add_all([post1, post2])
    db.commit()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Asama.ai"})


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "Asama.ai"}


@app.post("/api/register", response_model=Token)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    email = payload.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    user = User(name=payload.name, email=email, password_hash=get_password_hash(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists") from exc
    db.refresh(user)
    return Token(access_token=create_access_token(str(user.id)))


@app.post("/api/login", response_model=Token)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return Token(access_token=create_access_token(str(user.id)))


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat(),
    }


@app.get("/api/profile")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()


@app.post("/api/profile")
def create_profile(payload: BusinessProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile already exists for this user")

    profile = BusinessProfile(
        user_id=current_user.id,
        company_name=payload.company_name,
        industry=payload.industry,
        description=payload.description,
        products=payload.products,
        services=payload.services,
        location=payload.location,
        requirements=payload.requirements,
        interests=payload.interests,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.put("/api/profile")
def update_profile(payload: BusinessProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    if profile is None:
        profile = BusinessProfile(user_id=current_user.id)
        db.add(profile)

    profile.company_name = payload.company_name
    profile.industry = payload.industry
    profile.description = payload.description
    profile.products = payload.products
    profile.services = payload.services
    profile.location = payload.location
    profile.requirements = payload.requirements
    profile.interests = payload.interests
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/agents")
def list_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).all()
    return [
        {
            "id": agent.id,
            "user_id": agent.user_id,
            "name": agent.name,
            "industry": agent.industry,
            "summary": agent.summary,
            "business_goals": agent.business_goals,
            "interests": agent.interests,
            "location": agent.location,
            "created_at": agent.created_at.isoformat(),
        }
        for agent in agents
    ]


@app.get("/api/me/agents")
def list_my_agents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Agent).filter(Agent.user_id == current_user.id).order_by(Agent.created_at.desc()).all()


@app.post("/api/agents")
def create_agent(payload: AgentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = Agent(
        user_id=current_user.id,
        name=payload.name,
        industry=payload.industry,
        summary=payload.summary,
        business_goals=payload.business_goals,
        interests=payload.interests,
        location=payload.location,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@app.post("/api/posts")
def create_post(payload: PostCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    agent_query = db.query(Agent).filter(Agent.user_id == current_user.id)
    if payload.agent_id is not None:
        agent_query = agent_query.filter(Agent.id == payload.agent_id)
    agent = agent_query.order_by(Agent.created_at.desc()).first()
    if not agent:
        if payload.agent_id is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Choose one of your own AI agents to publish this update")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create an AI agent before posting updates")

    post = Post(
        agent_id=agent.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        requirements=payload.requirements,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_owned_post(post_id: int, owner_id: int, db: Session) -> Post:
    post = (
        db.query(Post)
        .join(Agent, Post.agent_id == Agent.id)
        .filter(Post.id == post_id, Agent.user_id == owner_id)
        .first()
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business update not found")
    return post


@app.put("/api/posts/{post_id}")
def update_post(
    post_id: int,
    payload: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = get_owned_post(post_id, current_user.id, db)
    post.title = payload.title
    post.description = payload.description
    post.category = payload.category
    post.requirements = payload.requirements
    db.commit()
    db.refresh(post)
    return serialize_post_summary(post)


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = get_owned_post(post_id, current_user.id, db)
    db.query(SavedPost).filter(SavedPost.post_id == post_id).delete(synchronize_session=False)
    db.delete(post)
    db.commit()
    return {"post_id": post_id, "deleted": True}


def serialize_post_summary(post: Post) -> dict:
    agent = post.agent
    owner = agent.user
    profile = owner.profile
    return {
        "id": post.id,
        "user_id": owner.id,
        "title": post.title,
        "description": post.description,
        "category": post.category,
        "requirements": post.requirements,
        "created_at": post.created_at.isoformat(),
        "agent_name": agent.name,
        "industry": agent.industry,
        "location": agent.location,
        "business_name": profile.company_name if profile else owner.name,
    }


@app.get("/api/posts")
def list_posts(db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .options(joinedload(Post.agent).joinedload(Agent.user).joinedload(User.profile))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(50)
        .all()
    )
    return [serialize_post_summary(post) for post in posts]


@app.get("/api/saved-posts")
def list_saved_posts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    saved_posts = (
        db.query(SavedPost)
        .options(
            joinedload(SavedPost.post)
            .joinedload(Post.agent)
            .joinedload(Agent.user)
            .joinedload(User.profile)
        )
        .filter(SavedPost.user_id == current_user.id)
        .order_by(SavedPost.saved_at.desc(), SavedPost.id.desc())
        .all()
    )
    return [
        {"saved_at": saved_post.saved_at.isoformat(), **serialize_post_summary(saved_post.post)}
        for saved_post in saved_posts
    ]


@app.post("/api/saved-posts/{post_id}")
def save_post(post_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business update not found")

    saved_post = (
        db.query(SavedPost)
        .filter(SavedPost.user_id == current_user.id, SavedPost.post_id == post_id)
        .first()
    )
    if saved_post is None:
        db.add(SavedPost(user_id=current_user.id, post_id=post_id))
        db.commit()
    return {"post_id": post_id, "saved": True}


@app.delete("/api/saved-posts/{post_id}")
def unsave_post(post_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business update not found")

    saved_post = (
        db.query(SavedPost)
        .filter(SavedPost.user_id == current_user.id, SavedPost.post_id == post_id)
        .first()
    )
    if saved_post is not None:
        db.delete(saved_post)
        db.commit()
    return {"post_id": post_id, "saved": False}


@app.post("/api/search")
def semantic_search(payload: SearchRequest, db: Session = Depends(get_db)):
    agents = (
        db.query(Agent)
        .options(
            joinedload(Agent.user).joinedload(User.profile),
            selectinload(Agent.posts),
        )
        .all()
    )
    if payload.industry:
        industry = payload.industry.casefold()
        agents = [
            agent
            for agent in agents
            if industry in agent.industry.casefold()
            or (
                agent.user.profile is not None
                and industry in agent.user.profile.industry.casefold()
            )
        ]
    if payload.location:
        location = payload.location.casefold()
        agents = [
            agent
            for agent in agents
            if location in (agent.location or "").casefold()
            or (
                agent.user.profile is not None
                and location in (agent.user.profile.location or "").casefold()
            )
        ]
    result = rank_agents_for_query(payload.query, agents)
    return {
        "query": payload.query,
        "filters": {"industry": payload.industry, "location": payload.location},
        "recommendations": result,
    }


@app.post("/api/connections")
def create_connection(payload: ConnectionRequestCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot connect with yourself")

    receiver = db.query(User).filter(User.id == payload.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver not found")

    existing_request = (
        db.query(ConnectionRequest)
        .filter(ConnectionRequest.status.in_(["pending", "accepted"]))
        .filter(
            or_(
                and_(
                    ConnectionRequest.sender_id == current_user.id,
                    ConnectionRequest.receiver_id == payload.receiver_id,
                ),
                and_(
                    ConnectionRequest.sender_id == payload.receiver_id,
                    ConnectionRequest.receiver_id == current_user.id,
                ),
            )
        )
        .first()
    )
    if existing_request:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending request or connection already exists")

    request_item = ConnectionRequest(
        sender_id=current_user.id,
        receiver_id=payload.receiver_id,
        note=payload.note,
        status="pending",
    )
    db.add(request_item)
    db.flush()
    db.add(
        Notification(
            user_id=receiver.id,
            type="connection_request",
            title="New connection request",
            body=f"{current_user.name} sent you a connection request.",
            related_user_id=current_user.id,
            connection_request_id=request_item.id,
        )
    )
    db.commit()
    db.refresh(request_item)
    return {"message": "Connection request sent", "request_id": request_item.id, "status": request_item.status}


@app.get("/api/connections")
def list_connections(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    requests = (
        db.query(ConnectionRequest)
        .filter(
            or_(
                ConnectionRequest.sender_id == current_user.id,
                ConnectionRequest.receiver_id == current_user.id,
            )
        )
        .order_by(ConnectionRequest.created_at.desc())
        .all()
    )

    incoming = []
    outgoing = []
    accepted = []
    for request_item in requests:
        is_sender = request_item.sender_id == current_user.id
        other_user = request_item.receiver if is_sender else request_item.sender
        item = {
            "id": request_item.id,
            "user_id": other_user.id,
            "name": other_user.name,
            "email": other_user.email,
            "note": request_item.note,
            "status": request_item.status,
            "created_at": request_item.created_at.isoformat(),
        }
        if request_item.status == "accepted":
            accepted.append(item)
        elif is_sender:
            outgoing.append(item)
        else:
            incoming.append(item)

    return {"incoming": incoming, "outgoing": outgoing, "connections": accepted}


@app.patch("/api/connections/{request_id}/respond")
def respond_to_connection(
    request_id: int,
    payload: ConnectionRequestResponse,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request_item = db.query(ConnectionRequest).filter(ConnectionRequest.id == request_id).first()
    if not request_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection request not found")
    if request_item.receiver_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the recipient can respond to this request")
    if request_item.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request has already been handled")

    request_item.status = payload.status
    status_text = "accepted" if payload.status == "accepted" else "declined"
    db.add(
        Notification(
            user_id=request_item.sender_id,
            type=f"connection_{payload.status}",
            title=f"Connection request {status_text}",
            body=f"{current_user.name} {status_text} your connection request.",
            related_user_id=current_user.id,
            connection_request_id=request_item.id,
        )
    )
    db.commit()
    db.refresh(request_item)
    return {"request_id": request_item.id, "status": request_item.status}


@app.get("/api/notifications")
def list_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(100)
        .all()
    )
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    ).count()
    return {
        "unread_count": unread_count,
        "notifications": [
            {
                "id": notification.id,
                "type": notification.type,
                "title": notification.title,
                "body": notification.body,
                "related_user_id": notification.related_user_id,
                "related_user_name": notification.related_user.name if notification.related_user else None,
                "connection_request_id": notification.connection_request_id,
                "message_id": notification.message_id,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            }
            for notification in notifications
        ],
    }


@app.patch("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"id": notification.id, "is_read": notification.is_read}


@app.get("/api/messages/{other_user_id}")
def list_messages(
    other_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if other_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot message yourself")

    is_connected = (
        db.query(ConnectionRequest)
        .filter(ConnectionRequest.status == "accepted")
        .filter(
            or_(
                and_(
                    ConnectionRequest.sender_id == current_user.id,
                    ConnectionRequest.receiver_id == other_user_id,
                ),
                and_(
                    ConnectionRequest.sender_id == other_user_id,
                    ConnectionRequest.receiver_id == current_user.id,
                ),
            )
        )
        .first()
    )
    if not is_connected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Messaging is available only to accepted connections")

    messages = (
        db.query(Message)
        .filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == other_user_id),
                and_(Message.sender_id == other_user_id, Message.receiver_id == current_user.id),
            )
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(200)
        .all()
    )
    messages.reverse()
    return [
        {
            "id": message.id,
            "sender_id": message.sender_id,
            "receiver_id": message.receiver_id,
            "body": message.body,
            "created_at": message.created_at.isoformat(),
        }
        for message in messages
    ]


@app.post("/api/messages", status_code=status.HTTP_201_CREATED)
def send_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.receiver_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot message yourself")

    receiver = db.query(User).filter(User.id == payload.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    is_connected = (
        db.query(ConnectionRequest)
        .filter(ConnectionRequest.status == "accepted")
        .filter(
            or_(
                and_(
                    ConnectionRequest.sender_id == current_user.id,
                    ConnectionRequest.receiver_id == payload.receiver_id,
                ),
                and_(
                    ConnectionRequest.sender_id == payload.receiver_id,
                    ConnectionRequest.receiver_id == current_user.id,
                ),
            )
        )
        .first()
    )
    if not is_connected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Messaging is available only to accepted connections")

    message = Message(
        sender_id=current_user.id,
        receiver_id=payload.receiver_id,
        body=payload.body,
    )
    db.add(message)
    db.flush()
    db.add(
        Notification(
            user_id=receiver.id,
            type="new_message",
            title="New message",
            body=f"You have a new message from {current_user.name}.",
            related_user_id=current_user.id,
            message_id=message.id,
        )
    )
    db.commit()
    db.refresh(message)
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "receiver_id": message.receiver_id,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }
