"""
Message definitions for the game server.
Each message has an encode function that returns bytes.
Field numbers are derived from the decompiled protobuf code.
"""
from pb import PBWriter, PBReader, encode_varint, encode_tag


# ============== HTTP Messages ==============

def encode_ret_login_msg(player_id, account, gate_addr, gate_key, is_bind=False):
    """RetLoginMsg: Id(1), IsBind(2), Account(3), QQId(4), GateAddr(5), GateKey(6)"""
    w = PBWriter()
    w.write_varint_field(1, player_id)
    w.write_bool_field(2, is_bind)
    w.write_string_field(3, account)
    # field 4 (QQId) skipped
    w.write_string_field(5, gate_addr)
    w.write_string_field(6, gate_key)
    return w.get_bytes()


def encode_ret_start_game(room_addr, room_key):
    """RetStartGame: RoomAddr(1), RoomKey(2)"""
    w = PBWriter()
    w.write_string_field(1, room_addr)
    w.write_string_field(2, room_key)
    return w.get_bytes()


def encode_error_response(err_code):
    """HTTP error response: flag byte (odd=error) + 4-byte error code (LE)"""
    return bytes([1]) + err_code.to_bytes(4, 'little')


def encode_http_success(pb_data):
    """HTTP success response: flag byte (even=success) + pb data"""
    return bytes([0]) + pb_data


# ============== Gate/RPC Messages ==============

def encode_ret_gate_login(key1=b'', key2=b''):
    """RetGateLogin: Key1(1,bytes), Key2(2,bytes)"""
    w = PBWriter()
    w.write_bytes_field(1, key1)
    w.write_bytes_field(2, key2)
    return w.get_bytes()


def encode_ret_heartbeat():
    """RetHeartBeat: empty"""
    return b''


def encode_ret_betick(betick):
    """RetBetick: Betick(1,uint32)"""
    w = PBWriter()
    w.write_varint_field(1, betick)
    return w.get_bytes()


# ============== User Module Messages ==============

def encode_msg_head_info(user_id=0, account="", male=False, head_url="", credit=0,
                         fans_num=0, sex=0, head_id=0, cup_num=0, level=1,
                         level_score=0, follow_num=0, liked_num=0, avatar_url=""):
    """MsgHeadInfo fields 1-19"""
    w = PBWriter()
    w.write_varint_field(1, user_id)
    w.write_string_field(2, account)
    # field 3 (Area) skipped
    w.write_bool_field(4, male)
    w.write_string_field(5, head_url)
    # field 6 (QQId) skipped
    w.write_varint_field(7, credit)
    w.write_varint_field(8, fans_num)
    w.write_varint_field(9, sex)
    w.write_varint_field(10, head_id)
    w.write_string_field(12, avatar_url)
    w.write_varint_field(15, cup_num)
    w.write_varint_field(16, level)
    w.write_varint_field(17, level_score)
    w.write_varint_field(18, follow_num)
    w.write_varint_field(19, liked_num)
    return w.get_bytes()


def encode_msg_qualifying_detail():
    """MsgQualifyingDetail - minimal valid structure"""
    w = PBWriter()
    w.write_varint_field(1, 1)  # Level
    w.write_varint_field(2, 0)  # Score
    w.write_varint_field(3, 0)  # PartyScore
    return w.get_bytes()


def encode_msg_map_info(map_id, map_name="", map_type=0):
    """MsgMapInfo: MapID(1), MapName(2), MapType(3)"""
    w = PBWriter()
    w.write_varint_field(1, map_id)
    w.write_string_field(2, map_name)
    w.write_varint_field(3, map_type)
    return w.get_bytes()


def encode_msg_player_ability(ability_level=1, birthday=0, age_level=0):
    """MsgPlayerAbility"""
    w = PBWriter()
    w.write_varint_field(1, ability_level)
    w.write_varint_field(2, birthday)
    w.write_varint_field(3, age_level)
    return w.get_bytes()


def encode_msg_occ_detail(occ_id=1):
    """MsgOccDetail"""
    w = PBWriter()
    w.write_varint_field(1, occ_id)
    return w.get_bytes()


def encode_ret_get_role_detail(player_id, account, game_name=""):
    """RetGetRoleDetail with all required fields for client to load"""
    w = PBWriter()
    # Field 1: Head (MsgHeadInfo)
    head_data = encode_msg_head_info(
        user_id=player_id,
        account=account,
        male=True,
        sex=1,
        head_id=1,
        level=1,
        cup_num=0
    )
    w.write_message_field(1, head_data)
    # Field 4: SpaceNum
    w.write_varint_field(4, 1)
    # Field 5: Pai
    w.write_varint_field(5, 100)
    # Field 6: Cookie
    w.write_varint_field(6, 10000)
    # Field 8: Donut
    w.write_varint_field(8, 100)
    # Field 9: IsRealNameAuth
    w.write_bool_field(9, True)
    # Field 10: Qualifying
    qual_data = encode_msg_qualifying_detail()
    w.write_message_field(10, qual_data)
    # Field 11: MapList
    map_data = encode_msg_map_info(1, "SpaceStation", 1)
    w.write_message_field(11, map_data)
    # Field 12: Ability
    ability_data = encode_msg_player_ability(1, 946684800, 18)  # 2000-01-01, age 18
    w.write_message_field(12, ability_data)
    # Field 15: ColorId
    w.write_varint_field(15, 1)
    # Field 16: OccupationList
    occ_data = encode_msg_occ_detail(1)
    w.write_message_field(16, occ_data)
    # Field 17: AttackEffect
    w.write_varint_field(17, 800001)
    # Field 19: OccCard
    w.write_varint_field(19, 1)
    return w.get_bytes()


def encode_ret_get_svr_time(svr_time):
    """RetGetSvrTime: SvrTime(1,uint64)"""
    w = PBWriter()
    w.write_varint_field(1, svr_time)
    return w.get_bytes()


def encode_ret_get_bag_data():
    """RetGetBagData - empty bag"""
    return b''


def encode_ret_follow_list():
    """RetFollowList - empty"""
    return b''


def encode_ret_fans_list():
    """RetFansList - empty"""
    return b''


def encode_ret_friend_list():
    """RetFriendList - empty"""
    return b''


def encode_ret_room_list():
    """RetRoomList - empty room list"""
    return b''


def encode_ret_get_box_store_house():
    """RetGetBoxStoreHouse"""
    return b''


def encode_ret_get_daily_chose():
    """RetGetDailyChose"""
    return b''


def encode_ret_mail_info():
    """RetMailInfo"""
    return b''


def encode_ret_new_fans_stat():
    """RetNewFansStat"""
    w = PBWriter()
    w.write_varint_field(1, 0)
    return w.get_bytes()


def encode_ret_new_message():
    """RetNewMessage"""
    w = PBWriter()
    return w.get_bytes()


def encode_ret_get_user_state():
    """RetGetUserState"""
    return b''


def encode_ret_qualifying_info():
    """RetGetQualifyingInfo"""
    return b''


def encode_ret_player_occupations():
    """RetPlayerOccupations"""
    w = PBWriter()
    occ = encode_msg_occ_detail(1)
    w.write_message_field(1, occ)
    return w.get_bytes()


def encode_ret_player_clothes():
    """RetPlayerClothes"""
    return b''


def encode_ret_get_like_record():
    """RetGetLikeRecord"""
    return b''


def encode_ret_get_visite_record():
    """RetGetVisiteRecord"""
    return b''


def encode_ret_interact_record():
    """RetInteractRecord"""
    return b''


def encode_ret_get_message_record():
    """RetGetMessageRecord"""
    return b''


def encode_ret_recommend_list():
    """RetRecommendList"""
    return b''


def encode_ret_recent_gamer():
    """RetRecentGamer"""
    return b''


def encode_ret_get_sim_user_info():
    """RetGetSimUserInfo"""
    return b''


def encode_ret_get_user_page():
    """RetGetUserPage"""
    return b''


def encode_ret_get_user_game_page():
    """RetGetUserGamePage"""
    return b''


def encode_ret_team_inv_list():
    """RetTeamInvList"""
    return b''


def encode_ret_nearby_players():
    """RetNearByPlayers"""
    return b''


def encode_ret_black_list():
    """RetBlackList"""
    return b''


def encode_ret_get_photo_list():
    """RetGetPhotoList"""
    return b''


def encode_ret_get_bbs_open_to():
    """RetGetBBSOpenTo"""
    return b''


def encode_ret_get_msg_board():
    """RetGetMsgBoard"""
    return b''


def encode_ret_get_msg_board_top():
    """RetGetMsgBoardTop"""
    return b''


def encode_ret_get_msg_board_hot():
    """RetGetMsgBoardHot"""
    return b''


def encode_ret_get_user_leave_msg():
    """RetGetUserLeaveMsg"""
    return b''


def encode_ret_follow_state():
    """RetFollowState"""
    return b''


def encode_ret_get_the_inviter():
    """RetGetTheInviter"""
    return b''


def encode_ret_id_card_verify():
    """RetIdCardVerify"""
    w = PBWriter()
    w.write_bool_field(1, True)
    return w.get_bytes()


# ============== Scene Server Messages ==============

def encode_msg_vector(x=0.0, y=0.0):
    """MsgVector: X(1,float), Y(2,float)"""
    w = PBWriter()
    w.write_float_field(1, x)
    w.write_float_field(2, y)
    return w.get_bytes()


def decode_msg_vector(data):
    """Decode a MsgVector from raw bytes. Returns (x, y)."""
    from pb import PBReader
    x, y = 0.0, 0.0
    try:
        reader = PBReader(data)
        while reader.has_more():
            field_num, wire_type = reader.read_tag()
            if field_num == 1 and wire_type == 5:  # X (float)
                x = reader.read_float()
            elif field_num == 2 and wire_type == 5:  # Y (float)
                y = reader.read_float()
            else:
                reader.skip_field(wire_type)
    except:
        pass
    return x, y


def encode_msg_player_info(player_id, name, x=0, y=0, z=0, color_id=1, state=0):
    """MsgPlayerInfo for scene"""
    w = PBWriter()
    w.write_varint_field(1, player_id)
    w.write_string_field(2, name)
    w.write_varint_field(3, color_id)
    w.write_varint_field(4, state)
    return w.get_bytes()


def encode_msg_scene(scene_id=1, map_id=1):
    """MsgScene"""
    w = PBWriter()
    w.write_varint_field(1, scene_id)
    w.write_varint_field(2, map_id)
    return w.get_bytes()


def encode_ret_scene_login(ok=True, player_id=1, scene_id=1, map_id=1, time=0):
    """RetSceneLogin: Ok(1,bool), PlayerId(2,uint64), SceneId(3,uint32),
    Time(4,uint32), Scene(5,msg), MapId(6,uint32), VoiceId(7,string),
    VoiceAddr(8,string), VoiceToken(9,string)"""
    w = PBWriter()
    w.write_bool_field(1, ok)
    w.write_varint_field(2, player_id)
    w.write_varint_field(3, scene_id)
    w.write_varint_field(4, time)
    scene_data = encode_msg_scene(scene_id, map_id)
    w.write_message_field(5, scene_data)
    w.write_varint_field(6, map_id)
    return w.get_bytes()


def encode_scene_heartbeat():
    """Scene heartbeat response - empty"""
    return b''


def encode_scene_add_del_player(players_added, players_removed):
    """AddDelPlayer message"""
    w = PBWriter()
    for p in players_added:
        info = encode_msg_player_info(p['id'], p['name'], p.get('x', 0), p.get('y', 0))
        w.write_message_field(1, info)  # added players
    for p in players_removed:
        w.write_varint_field(2, p['id'])  # removed players
    return w.get_bytes()


def encode_scene_update_player(player_id, x, y, z, state=0):
    """UpdatePlayer message"""
    w = PBWriter()
    w.write_varint_field(1, player_id)
    w.write_varint_field(2, int(x * 1000))
    w.write_varint_field(3, int(y * 1000))
    w.write_varint_field(4, int(z * 1000))
    w.write_varint_field(5, state)
    return w.get_bytes()


def encode_scene_game_progress(progress=0):
    """GameProgressNotice"""
    w = PBWriter()
    w.write_varint_field(1, progress)
    return w.get_bytes()


def encode_scene_chat(player_id, name, content, chat_type=0):
    """MsgSceneChat"""
    w = PBWriter()
    w.write_varint_field(1, player_id)
    w.write_string_field(2, name)
    w.write_string_field(3, content)
    w.write_varint_field(4, chat_type)
    return w.get_bytes()


def encode_scene_error_msg(error_code=0, msg=""):
    """ErrorMsg"""
    w = PBWriter()
    w.write_varint_field(1, error_code)
    w.write_string_field(2, msg)
    return w.get_bytes()


def encode_scene_room_close():
    """RoomClose"""
    return b''
