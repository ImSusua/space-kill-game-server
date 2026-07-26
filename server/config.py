"""
Server configuration.
"""
import socket
import os

def get_local_ip():
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# The IP that will be configured in the APK
APK_IP = "172.21.26.128"

# For testing, use local IP
LOCAL_IP = get_local_ip()

# Servers always bind to 0.0.0.0 (all interfaces) in server.py.
# The addresses below are sent TO the APK client, so they must always
# use the APK_IP that the APK is configured to connect to.
SERVER_IP = APK_IP  # Always 172.21.26.128 - matches patched APK

# Port configuration
HTTP_PORT = 8080
GATE_PORT = 8100
SCENE_PORT = 8200

# Server addresses (sent to APK client in login/startgame responses)
HTTP_ADDR = f"{SERVER_IP}:{HTTP_PORT}"
GATE_ADDR = f"{SERVER_IP}:{GATE_PORT}"
SCENE_ADDR = f"{SERVER_IP}:{SCENE_PORT}"

# Module types (from decompiled code)
class ModuleType:
    Login = 1
    User = 2
    Scene = 3
    Team = 4
    Bag = 5
    Chat = 6
    UGC = 7
    Rank = 8
    GEO = 9
    BBS = 10
    Clothes = 11
    Qualifying = 13
    Watch = 16
    Shop = 17
    Other = 26
    Room = 27
    Watcher = 28
    Gift = 29
    Relation = 30
    Newbie = 31
    Activity = 32
    Dialog = 50000
    LocalStore = 50001
    PushService = 60000
    ControlService = 60001
    GateService = 60002
    VCenterService = 60003
    WatcherService = 60004
    RCenterService = 60005
    GmService = 60006
    WCenterService = 60007

# Gate commands
class GateCmd:
    GateUnusedCmd = 0
    GateLogin = 1
    HeartBeat = 2
    GateErrCode = 3
    Betick = 4

# Login commands
class LoginCmd:
    LoginUnusedCmd = 0
    Login = 1
    StartGame = 2
    ErrorMsg = 3
    Bind = 4
    VerificationCode = 5
    ResetPasswordLogout = 6
    BindThird = 7
    ThirdShareId = 8

# Scene commands
class SceneCmd:
    SceneCmdNone = 0
    Login = 1
    HeartBeat = 2
    Scene = 3
    ErrorMsg = 4
    Action = 5
    AddDelPlayer = 6
    UpdatePlayer = 7
    ChangeOwner = 8
    BatchUpdatePlayer = 9
    GameProgressNotice = 10
    SpeakerNotice = 11
    UpdateKillerCooldowns = 12
    UpdateClearBody = 13
    WatchLogin = 15
    WatchNotice = 16
    RefreshScene = 17
    RoomClose = 18
    UpdateSceneObjs = 19
    Barrage = 21
    HideBarrage = 22
    AddLike = 23
    RoomDress = 24
    WatchLikeRank = 25
    RetAddLike = 26
    CustomSetting = 27
    CustomChangeLabel = 28
    UpdateBag = 29
    VoiceInfo = 30
    BatchMove = 50
    Move = 51
    ChangeState = 53
    SyncAction = 54
    Operate = 55
    OwnerOprate = 56
    GameOprate = 57
    GetRoomSetting = 58
    RoomSetting = 59
    RoomChat = 60
    Trigger = 61
    SendEmoji = 62
    GiveGift = 63
    ReportHangUp = 64
    RoomBroadcast = 65
    ReportSpeak = 66
    GameKick = 67
    MuteSpeak = 68
    ModifyRoomName = 69
    ChangeColor = 70
    BatchTrigger = 71
    MoveObject = 72
    RefreshData = 73
    RefreshCustomSetting = 74
    RefreshCustomLabels = 75
    RoomAIAudio = 76
    SyncMove = 77
    SpaceStart = 81
    SpaceEnd = 82
    SpaceKill = 83
    SpaceReport = 84
    SpaceUpdatePlayer = 85
    SpaceVote = 86
    SpaceVoteEnd = 87
    SpaceStage = 88
    StartTinyGame = 89
    FinishTinyGame = 90
    MissionTotalProcess = 91
    BreakDevice = 92
    SpaceEnterVent = 93
    DeviceStartCD = 95
    AddMission = 96
    CancelTinyGame = 97
    PlayTinyGame = 98
    ChoseIdentity = 99
    NoticeIdentity = 100
    SpaceChosePos = 101
    SpaceChoseArea = 102
    RemoteUrgent = 103
    EndSpeak = 104
    SpaceClearBody = 105
    SpaceSample = 106
    SpaceMorph = 107
    SpaceMorphEnd = 108
    UseOccupationCard = 109
    SpaceCheckQuit = 110
    UGCStart = 111
    UGCEnd = 112
    SpaceChoseArea = 102

# User commands
class UserCmd:
    UserUnusedCmd = 0
    GetRoleDetail = 1
    PushTest = 3
    SeePlayer = 4
    InvitePlayer = 5
    RefusePlayer = 6
    ReceiveInvite = 7
    WatchList = 8
    ReceiveRefuse = 9
    UserFeedback = 10
    SetUserSetting = 11
    ChangeAccount = 12
    VerifyPasswd = 13
    ChangePasswd = 14
    GetSimUserInfo = 15
    GetUserPage = 16
    GetVisiteRecord = 17
    DelVisiteRecord = 18
    GetLikeRecord = 19
    AbuseDislike = 20
    GetMessageRecord = 21
    UserLike = 22
    NewMessage = 23
    AudioPlay = 24
    RecvHeadAward = 25
    DelAudio = 26
    SetAge = 27
    SetSex = 28
    SetSign = 29
    GetUserGamePage = 30
    GetPhotoList = 31
    ShowPhoto = 32
    DelPhoto = 33
    SetHead = 34
    InteractRecord = 36
    HeadUser = 37
    CupReceivedAwards = 38
    ReceiveCupAward = 39
    AwardNotice = 40
    AbuseDetails = 41
    GetTodayKillerPrice = 42
    InitAbility = 43
    FigureShow = 44
    CorrectAgeLevel = 45
    InitAgeLevel = 46
    LogicOnline = 51
    LogicOffline = 52
    RegisterAcc = 53
    VerificationCode = 54
    ChangeBindTelStep1 = 55
    ChangeBindTelStep2 = 56
    ResetPasswordByTel = 57
    CheckTel = 58
    SetColor = 59
    GetBoxStoreHouse = 61
    OpenBox = 62
    AwardBox = 63
    GetDailyChose = 66
    BuyDailyChose = 67
    SetCoverPhoto = 70
    LaudPhoto = 71
    PlayerOccupations = 72
    SetAttackEffect = 73
    PlayerClothes = 74

# Bag commands
class BagCmd:
    BagUnusedCmd = 0
    GetBagData = 1
    UseItem = 2
    UpdateBag = 3
    UpdateOccupation = 4
    ChangeOccCard = 5

# Relation commands
class RelationCmd:
    RelationUnusedCmd = 0
    AddFollow = 1
    FollowList = 2
    FansList = 3
    FriendList = 4
    CancelFollow = 5
    FollowState = 6
    BatchRelation = 7
    RecentGamer = 8
    SearchAccount = 9
    ReadNewMessage = 10
    SkipNewFans = 11
    NewFansStat = 12
    NewFansNotice = 13
    AddAlias = 14
    RecommendList = 15
    GetSvrTime = 16
    GetTheInviter = 17
    RecommendPlayers = 18
    NoticeFollow = 19

# Room commands
class RoomCmd:
    RoomUnusedCmd = 0
    RoomList = 1
    RoomOperate = 2
    RoomPlayerOpState = 3
    Praise = 4
    TypeRoomList = 5

# Shop commands
class ShopCmd:
    ShopUnusedCmd = 0
    ShopClothesBuy = 1
    DressUp = 2
    TakeOffClothes = 3

# Other commands
class OtherCmd:
    OtherUnusedCmd = 0
    LongToShortUrl = 1
    AddReport = 2
    DelAudience = 3
    InitELO = 4
    GetUserState = 5
    IdCardVerify = 6
    UpdateLoginSession = 7
    ShareVideoInfo = 8
    ShareVideoReward = 9
    ShareVideoUpload = 10
    ShareVideoThirdInfo = 11
    Redpoints = 12
    RedpointsNotice = 13

# Gift commands
class GiftCmd:
    GiftUnusedCmd = 0
    GetReceiveGift = 1
    GiveGift = 2
    SendChatMsg = 3
    ReceiveGift = 4
    SendEmoji = 5

# Chat commands
class ChatCmd:
    ChatUnusedCmd = 0
    FriendSet = 1
    InPut = 2
    GetFriendSet = 3
    DeleteChat = 4

# BBS commands
class BBSCmd:
    BBSUnusedCmd = 0
    GetMsgBoard = 1
    GetMsgBoardTop = 2
    GetMsgBoardHot = 3
    GetUserLeaveMsg = 4
    GetTheLeaveMsg = 5
    GetTheMsgReply = 6
    GetDelMsgBoard = 7
    GetReplyMe = 8
    LeaveMsg = 9
    ReplyLeaveMsg = 10
    TopLeaveMsg = 11
    UnTopLeaveMsg = 12
    DelLeaveMsg = 13
    DelSomeoneMsg = 14
    StarLeaveMsg = 15
    UnStarLeaveMsg = 16
    SetBBSOpenTo = 17
    GetBBSOpenTo = 18
    Private = 19

# Mail commands
class MailCmd:
    MailCmdUnunsed = 0
    GetMailData = 1
    DoMailOp = 2
    SendMail = 3

# Qualifying commands
class QualifyingCmd:
    QualifyingUnusedCmd = 0
    GetQualifyingInfo = 1
