"""Operations on actual submitted state for the cross-day revision.

Receipts report local state and communication, never semantic acceptance.
"""

from copy import deepcopy
import hashlib
import json


def item(identifier, text, kind="receipt", **extra):
    return dict(id=identifier, text=text, kind=kind, channel=extra.pop("channel", "private"),
                editable=False, **extra)


def calculate(kind, resources, at):
    if kind == "lh_room_digest_release":
        draft=resources["room-digest"]
        ready=draft.get("fields",{}).get("ready") and draft.get("status")=="published"
        release=item("released-room-digest",draft["text"] if ready else "No approved active digest was released.",
                     "delivery" if ready else "receipt",channel="public" if ready else "private",
                     recipient="digest-readers" if ready else None,released=bool(ready),
                     assets=deepcopy(draft.get("assets",[])) if ready else [],released_at=at)
        return dict(effect=dict(add=[release]))

    if kind == "lh_gate_obstruction":
        routes=deepcopy(resources["route-records"]["routes"])
        routes["R2"]["clearances_cm"]=[90,78,95]
        text=resources["route-records"]["text"].replace("middle corridor 85 cm","middle corridor 78 cm")
        return dict(effect=dict(patch={"route-records":dict(routes=routes,text=text)},add=[
            item("gate-condition","Actual gate check: R2 middle clearance now78cm due temporary obstruction. "
                 "Other supplied route dimensions unchanged; cart remains80cm.")]))

    if kind == "lh_escort_window":
        availability=deepcopy(resources["escort-records"]["availability"])
        availability["Kai"]=[635,665]
        return dict(effect=dict(patch={"escort-records":dict(availability=availability,
            text="Actual current escort windows: Jo10:25–10:40; Kai10:35–11:05. Both eligible; old reservations do not extend these real intervals.")},add=[
            item("escort-confirmation","Actual current Kai duty is10:35–11:05; earlier availability is superseded. "
                 "Existing local reservation records its old request until explicitly amended.")]))

    if kind == "lh_escort_reserve":
        draft=deepcopy(resources["route-plan"]["fields"])
        available=resources["escort-records"]["availability"][draft["escort"]]
        s,e=draft["escort_start"],draft["escort_end"]
        if not available[0]<=s<e<=available[1]:
            return dict(facts=dict(reserved=False,requested=[s,e],availability=available,prior_reservation_unchanged=True))
        actual=dict(route=draft["repair"],escort=draft["escort"],start=s,end=e)
        return dict(effect=dict(patch={"actual-escort":dict(fields=actual,text="Actual local escort reservation for requested route/person/interval.")}),
                    facts=dict(reserved=True,reservation=actual,cart_fit_audited=False,whole_trip_audited=False))

    if kind == "lh_crew_result":
        draft=resources["crew-departure-plan"]["fields"]
        selected=resources["route-records"]["routes"][draft["repair"]]
        actual=resources["actual-escort"].get("fields",{})
        width=min(selected["clearances_cm"])
        duration=selected["traversal_minutes"]
        covered=(actual.get("route")==draft["repair"] and actual.get("start",9999)<=635 and actual.get("end",-1)>=635+duration)
        text=("Actual crew used "+draft["repair"]+" with whole escort and reached the repair point10:55; no physical repair completion is recorded."
              if width>=80 and covered else "Actual crew route could not be completed: selected bottleneck or actual full-trip escort was insufficient. Repair-point arrival is unconfirmed.")
        return dict(effect=dict(add=[item("crew-route-result",text,selected_route=draft["repair"],
            actual_clearances=deepcopy(selected["clearances_cm"]),actual_escort=deepcopy(actual),traversal_minutes=duration,repair_performed=False)]))

    if kind in ("lh_recap_editor_proof","lh_recap_correct_proof"):
        correcting=kind=="lh_recap_correct_proof"
        queued=resources["actual-edit-queue"].get("fields",{})
        if not correcting and not queued.get("queued"):
            return dict(effect=dict(add=[item("returned-recap-proof","No editing tasks were actually queued; no proof was returned.",fields={})]))
        if correcting:
            a=deepcopy(resources["recap-a"]);b=deepcopy(resources["recap-b"])
            asset=deepcopy(resources["recap-image"])
        else:
            snaps=queued.get("content_snapshots",{})
            a=deepcopy(snaps.get("A-caption",{}));b=deepcopy(snaps.get("B-summary",{}))
            asset=deepcopy(resources["shared-frame"])
            b["text"]="B discussion recap: everyone was hopeful and agreed the meeting would happen."
        asset.update(id="proof-recap-image",kind="attachment",channel="public",editable=False)
        a["assets"]=["proof-recap-image"]
        fields=dict(A=dict(text=a.get("text",""),assets=a["assets"],actual_image_snapshot=deepcopy(asset)),B=dict(text=b.get("text",""),assets=[]),
                    source="creator-current" if correcting else "actual-operator-output",returned_at=at)
        identifier="sys-creator-proof-"+str(at) if correcting else "returned-recap-proof"
        proof=item(identifier,"Actual versioned proof; content is not a rights or semantic approval.",fields=fields)
        effect=dict(add=[asset,proof])
        if correcting:effect["patch"]={"corrected-proof-record":dict(fields=dict(proof_id=identifier))}
        return dict(effect=effect,facts=dict(proof_id=proof["id"],creator_local_correction=correcting,operator_new_work_performed=False))

    if kind == "lh_recap_b_feedback":
        proof=resources.get("returned-recap-proof",{}).get("fields",{})
        text=("The original returned operator proof says everyone was hopeful. That is not our intended two different views; "
              "please preserve our actual nonidentifying viewpoints and no private attributed quotation." if proof else
              "No actual proof has returned. We still need a faithful nonidentifying summary of our two distinct views.")
        return dict(effect=dict(add=[item("b-viewpoint-followup",text,"dm",author="B-organizer",recipient="B-organizer")]))

    if kind == "lh_recap_release":
        use_proof=resources["recap-release-choice"]["fields"]["source"]=="proof"
        if use_proof:
            corrected=resources["corrected-proof-record"]["fields"]["proof_id"]
            content=deepcopy(resources.get(corrected or "returned-recap-proof",{}).get("fields",{}))
            a=content.get("A",{});b=content.get("B",{})
        else:
            a=resources["recap-a"];b=resources["recap-b"]
        if not a.get("text") or not b.get("text") or (not use_proof and
                (a.get("status")!="published" or b.get("status")!="published")):
            return dict(effect=dict(add=[item("released-recaps","No complete prepared/published selected recap pair "
                "was available; no scheduled public release occurred.",released=False)]))
        assets=deepcopy(a.get("assets",[]))
        release=item("released-recaps",a.get("text","")+"\n\n"+b.get("text",""),"delivery",channel="public",
                     status="published",recipient="recap-readers",assets=assets,
                     actual_asset_contents={rid:deepcopy(resources[rid]) for rid in assets},
                     selected_source="proof" if use_proof else "authored",released_at=at)
        return dict(effect=dict(add=[release]))

    if kind == "lh_stock_reserve":
        plan=resources["allocation-board"]["fields"]
        stock=resources["packed-stock"]["fields"]
        requested={"a":plan["a"],"b":plan["b"]}
        mixed=sum({"mixed12":12,"mixed10":10}.get(v,0) for v in requested.values())
        veg=sum(8 if v=="vegetarian8" else 0 for v in requested.values())
        ok=mixed<=stock["mixed"] and veg<=stock["vegetarian"]
        if not ok:return dict(facts=dict(reserved=False,requested=requested,packed=deepcopy(stock),
                             reason="Requested quantities exceed actual packed stock; prior reservation unchanged."))
        return dict(effect=dict(patch={"actual-reservation":dict(fields=requested)}),
                    facts=dict(reserved=True,actual=requested,packed=deepcopy(stock),collected=False))

    if kind in ("lh_stock_mixed_pickup", "lh_stock_vegetarian_pickup"):
        reservation=deepcopy(resources["actual-reservation"]["fields"])
        stock=resources["packed-stock"]["fields"]
        vegetarian=kind=="lh_stock_vegetarian_pickup"
        collected={}
        for table,choice in reservation.items():
            if (choice=="vegetarian8") != vegetarian or choice not in ("mixed12","mixed10","vegetarian8"):
                continue
            count={"mixed12":12,"mixed10":10,"vegetarian8":8}.get(choice,0)
            available=stock["vegetarian"] if choice=="vegetarian8" else stock["mixed"]
            collected[table]=dict(reserved_choice=choice,actual_portions=min(count,available))
        identifier="vegetarian-pickup-receipt" if vegetarian else "mixed-pickup-receipt"
        receipt=item(identifier,"Actual local pickup record; not delivery or serving." if collected else
                     "No actual collection in this pickup window: no corresponding stock was reserved.",
                     reservation=reservation,collected=collected,picked_up_at=at if collected else None,
                     window_checked_at=at)
        previous=deepcopy(resources.get("pickup-receipt",{}).get("collected",{}))
        previous.update(collected)
        index=item("pickup-receipt","Current index of actual collections; each original timed receipt remains immutable.",
                   collected=previous,latest_receipt=identifier,indexed_at=at)
        return dict(effect=dict(add=[receipt,index]))

    if kind == "lh_tasting_followup":
        b=resources["actual-reservation"]["fields"]["b"]
        if b=="vegetarian8":text="Our accepted vegetarian eight remains its own format/count, yes? A's short mixed pack must not silently use our stock."
        elif b=="cancelled":text="Someone kept the original two-full-box promise. With tasting cancelled, should our social gathering still expect food? Please confirm the actual plan rather than the saved old promise."
        else:text="What tasting format and stock are actually committed for B? I have no supported confirmed reservation in this record; please preserve the separate social gathering."
        return dict(effect=dict(add=[item("b-setup-question",text,"dm",author="organizer-b",recipient="organizer-b",actual_reserved_b=b)]))

    if kind == "lh_workshop_log":
        fmt=resources["format-board"]["fields"]["format"]
        accepted="host-acceptance" in resources
        operator=resources["actual-operator"]["fields"]["assignment"]
        if fmt=="text-led" and accepted:
            text="Actual supported session: host-accepted text-led chat18:00–18:30; no captioned audio or replay."
        elif fmt=="audio-captions" and operator!="none":
            text="Actual audio caption service18:00–18:20 only;18:20–18:30 not captioned. No replay permission recorded."
        else:text="No actually host-accepted full text format or complete caption support is recorded; full session access unresolved."
        return dict(effect=dict(add=[item("actual-support-log",text,format=fmt,host_text_acceptance=accepted,
                                         local_operator_assignment=operator,recording_permission=False,reported_at=at)]))

    if kind == "lh_room_propose":
        draft=deepcopy(resources["room-plan"]["fields"])
        state=resources["room-service-state"]["fields"]
        pid="sys-lh-room-proposal-"+str(at)
        proposal=item(pid,"Exact joint-room proposal snapshot, not acceptance or reservation.","delivery",
                      delivery_type="room_proposal",recipient="participants",fields=draft,sent_at=at)
        events=[]
        for who,ok in (("A",draft["start"]>=state["a_arrival"] and draft["end"]-draft["start"]>=30),
                       ("B",draft["end"]<=state["b_departure"] and draft["end"]-draft["start"]>=30)):
            answer=item("sys-lh-room-"+who+"-"+str(at),"I accept this exact proposed conversation interval, subject to actual venue and budget."
                        if ok else "This exact interval does not satisfy my current availability/minimum duration.",
                        "dm",author=who,recipient=who,proposal_id=pid,proposal=draft,accepted_interval=ok)
            events.append(dict(id="lh-room-answer-"+who+"-"+str(at),at=at+1,add=[answer]))
        return dict(effect=dict(add=[proposal],patch={"sent-room-proposal":dict(fields=draft,proposal_id=pid,text="Latest exact proposal sent; all historical proposals remain.")}),
                    events=events,facts=dict(proposal_id=pid,delivered_to=["A","B"],acceptance_pending=True))

    if kind == "lh_room_reserve":
        draft=deepcopy(resources["room-plan"]["fields"])
        state=resources["room-service-state"]["fields"]
        s,e=draft["start"],draft["end"]
        room=draft["room"]
        setup,clear=(state["setup"],state["clearance"]) if room=="C" else (0,0)
        access_start,access_end=s-setup,e+clear
        cost=70-(15 if draft["joint_credit"]=="claim" else 0) if room=="C" else 40
        window=(990,1050) if room=="C" else (960,1020)
        valid=(window[0]<=access_start<s<e<=access_end<=window[1] and e-s>=30 and
               s>=state["a_arrival"] and e<=state["b_departure"] and cost<=60)
        proposals=[r for r in resources.values() if r.get("delivery_type")=="room_proposal" and r.get("fields")==draft]
        consented=None
        for p in proposals:
            accepted={r.get("author") for r in resources.values() if r.get("proposal_id")==p["id"] and r.get("accepted_interval") is True}
            if {"A","B"}<=accepted:consented=p;break
        if not valid or consented is None:
            return dict(facts=dict(reserved=False,current_draft=draft,actual_access=[access_start,access_end],
                        price=cost,reason="Current service constraints or matching actual same-proposal consents not met; earlier reservation unchanged."))
        actual=dict(**draft,access_start=access_start,access_end=access_end,cost=cost,accepted_proposal_id=consented["id"],reserved_at=at)
        return dict(effect=dict(patch={"actual-room-reservation":dict(fields=actual,text="Actual local amended room hold; no payment.")}),
                    facts=dict(reserved=True,reservation=actual,payment_taken=False))

    if kind == "lh_credit_release":
        queued=resources["release-queue"]["fields"]["status"] == "queued"
        result=item("actual-credit-release",resources["queued-file"]["text"] if queued else
                    "Optional release was actually cancelled; no promotion was published.",
                    "delivery" if queued else "receipt",channel="public" if queued else "private",
                    published=queued,recipient="promotion-readers" if queued else None,published_at=at)
        effect=dict(add=[result])
        if queued:
            fields=deepcopy(resources["release-queue"]["fields"])
            fields["status"]="released"
            effect["patch"]={"release-queue":dict(fields=fields)}
        return dict(effect=effect)

    if kind == "lh_helper_send":
        who=resources["access-state"]["fields"]["minimal_view"]
        if who == "none":return dict(facts=dict(delivered=False,recipient=None))
        slots=deepcopy(resources["minimal-schedule"]["fields"]["slots"])
        fields=dict(recipient=who,slots=slots,fields_shared=["initial","time"],sent_at=at)
        copy=item("sys-helper-copy-"+str(at),"Actual detached minimum schedule delivered; technical delivery is not identity verification.",
                  "delivery",recipient=who,delivery_type="helper_schedule_copy",fields=fields)
        return dict(effect=dict(add=[copy],patch={"actual-schedule-delivery":dict(fields=fields,text="Latest service-generated minimum scheduling snapshot; later direct messages may supersede this historical copy.")}),facts=fields)

    if kind == "lh_helper_followup":
        deliveries=[r for r in resources.values() if r.get("delivery_type")=="helper_schedule_copy"]
        if not deliveries:return dict(effect=dict(add=[]))
        first=min(deliveries,key=lambda r:r["fields"]["sent_at"])
        who=first["recipient"]
        question=item("held-schedule-question","I have the earlier scheduling copy and any updates actually "
                      "sent to me. Which time should I use after the applicant change? May I request a "
                      "full dossier/assessments for context?","dm",author=who,recipient=who,
                      original_copy_id=first["id"])
        return dict(effect=dict(add=[question]))

    if kind == "lh_worksheet_copy":
        deliveries=[r for r in resources.values() if r.get("linked_resource") in ("html-sheet","worksheet-file")]
        delivery=min(deliveries,key=lambda r:r.get("created_at",0)) if deliveries else None
        source=resources.get(delivery["linked_resource"],{}) if delivery else {}
        copy=item("copied-worksheet",source.get("text","") if delivery else "No actual worksheet delivery is available to copy.",
                  available=bool(delivery),source_id=source.get("id"),delivery_id=delivery["id"] if delivery else None,
                  units=deepcopy(source.get("units")),copied_at=at)
        return dict(effect=dict(add=[copy]))

    if kind == "lh_lesson_use":
        all_deliveries = [r for r in resources.values() if r.get("kind") == "reply" and
                         r.get("parent") in ("lesson-request","worked-question","lake-use-question") and r.get("linked_resource")]
        deliveries = [r for r in all_deliveries if r.get("created_at",0)<1440]
        revised = [r for r in all_deliveries if r.get("source_resource") in ("source-f57","source-f55")]
        snapshot = item("actual-lake-delivery", "Actual earlier recipient deliveries, not an assumption of current compatibility.",
                        deliveries=[dict(message_id=r["id"],recipient=r.get("recipient"),
                                         resource=r["linked_resource"],source=r.get("source_resource"),
                                         text=resources.get(r["linked_resource"],{}).get("text")) for r in deliveries])
        question = item("lake-use-question", ("I see revised files as well as the original delivery. Please explain "
                         "which labelled coherent edition applies to the class now." if revised else
                         "The class is using the corrected map with east bridge closed as well. "
                         "The earlier copies listed in actual-lake-delivery use the old constraints. Which current "
                         "permitted complete unit should I use?" if deliveries else
                         "The class now uses the corrected two-closure map, but I have not received a complete unit yet."),
                        "comment",channel="public",author="reader-len",recipient="reader-len")
        return dict(effect=dict(add=[snapshot,question]))

    if kind == "lh_voucher_quote":
        selection=deepcopy(resources["quote-plan"]["fields"])
        eligible=selection["store"] == "North"
        meal=24 if eligible else 32
        courier=resources["fee-state"]["fields"]["courier"] if selection["channel"] == "delivery" else 0
        quote=dict(**selection,voucher_eligible=eligible,meal=meal,courier=courier,total=meal+courier,
                   order_placed=False,quoted_at=at)
        return dict(effect=dict(patch={"actual-quote":dict(fields=quote,text="Actual unpurchased current store/channel quote.")}),facts=quote)

    if kind == "lh_voucher_followup":
        offers=[r for r in resources.values() if r.get("delivery_type") == "voucher_offer"]
        question=item("budget-followup",("The earlier actual offer is recorded in its own snapshot. Can that "
                      "24 pickup acceptance now cover a delivery within my28 budget after expiry?" if offers else
                      "There was no purchase/offer from me. With the updated courier fee, can the24 meal now be "
                      "delivered within my28 budget?"),"dm",author="reader",recipient="reader",
                      actual_offer_ids=[r["id"] for r in offers])
        return dict(effect=dict(add=[question]))

    if kind == "lh_album_preview":
        route=resources["album-route"]["fields"]["route"]
        migrated=resources["archive-phase"]["fields"]["state"] == "after"
        mapping={"J":("f21","P9",4,False),"K":("f08","P6",1,False),
                 "L":("project-landing",None,None,False) if migrated else ("f17","P6",2,False),
                 "M":("f34","P6",3,True)}
        if migrated:mapping["N"]=("f17","P6",2,False)
        if route not in mapping:raise ValueError("No currently registered target for this route")
        target,project,revision,signin=mapping[route]
        actual=dict(route=route,target=target,project=project,revision=revision,sign_in_required=signin,
                    status="published",text="Actual route "+route+" resolves to "+target+"; "+
                    ("owner sign-in required." if signin else "public access."))
        return dict(effect=dict(patch={"album-link":actual}),facts={k:v for k,v in actual.items() if k!="text"})

    if kind == "lh_album_followup":
        first=resources.get("album-delivered-card")
        saved_route=first.get("route") if first else None
        outcomes={"L":"I followed the original delivered L route; now I reach a landing page, not the album.",
                  "J":"The original delivered route shows the market/clock/bus sequence, not my harbour sequence.",
                  "K":"The original delivered archive is the older caption edition, not current release.",
                  "M":"The original delivered route asks for owner sign-in."}
        text=outcomes.get(saved_route,"I still need an actually delivered usable current public harbour-album route.")
        question=item("album-access-question",text+" Please keep my requested released sequence distinct from the teaser.",
                      "dm",author="reader",recipient="reader",original_card_id="album-delivered-card" if first else None,
                      original_route=saved_route)
        return dict(effect=dict(add=[question]))

    if kind == "lh_exercise_use":
        deliveries = [r for r in resources.values() if r.get("linked_resource") in
                      ("html-exercise", "exercise-file") and r.get("kind") == "reply"]
        deliveries.sort(key=lambda r:r.get("created_at",0))
        delivery = deliveries[0] if deliveries else None
        target = resources.get(delivery.get("linked_resource"),{}) if delivery else {}
        available = bool(delivery and target.get("status","published") == "published")
        copied = item("actual-learner-copy", target.get("text","") if available else
                      "No currently available actually delivered public exercise could be copied.",
                      delivery_id=delivery["id"] if delivery else None,
                      source_id=target.get("id"),available=available,copied_at=at)
        question = item("learner-reasoning",
                        ("I used the exercise copy recorded in actual-learner-copy. I assumed dotted paths "
                         "were public and used that segment. Is my reasoning supported by the actual copy? "
                         "Please keep my work private." if available else
                         "I have no available delivered exercise copy. Please provide the public prerequisite "
                         "material through the actual delivery route; I cannot yet submit meaningful reasoning."),
                        "dm",author="learner",recipient="learner",copy_id="actual-learner-copy")
        return dict(effect=dict(add=[copied,question]))

    if kind == "lh_preserve_draft":
        fields = resources["harbor-state"]["fields"]
        saved = bool(fields["draft_retained"])
        result = item("preservation-result", "Actual local persistent copy saved from the retained owned draft."
                      if saved else "No retained draft existed; no persistent copy or deleted work was recovered.",
                      saved=saved, copy_id="local-copy-" + str(at) if saved else None, saved_at=at)
        effect = dict(add=[result])
        if saved:
            updated = deepcopy(fields)
            updated["draft"] = "saved"
            effect["patch"] = {"harbor-state":dict(fields=updated)}
        return dict(effect=effect,facts=dict(saved=saved,copy_id=result["copy_id"]))

    if kind == "lh_typing_retry":
        persisted = bool(resources.get("preservation-result",{}).get("saved"))
        fields = deepcopy(resources.get("harbor-state",{}).get("fields",dict(role="owner",input_lock="locked",draft="unsaved",draft_retained=True)))
        if not persisted:
            fields.update(draft="lost_after_restart",draft_retained=False)
        fields["input_lock"] = "unlocked"
        result = item("retry-result", "Next-day local retry accepts input. " +
                      ("The actual saved persistent copy remains available; input success did not create that save."
                       if persisted else "No persistent copy existed at restart; the previous unsaved work is unavailable."),
                      persisted_copy_available=persisted,original_retained=fields["draft_retained"])
        current=item("harbor-state","Actual owned local draft state after overnight restart.","record",fields=fields)
        return dict(effect=dict(add=[result,current]))

    if kind == "lh_support_status":
        active = resources["case-board"]["fields"]["original"] == "open"
        return dict(effect=dict(add=[
            item("actual-appointment", "Coordinator batch appointment disposition; later local board edits do not rebook a cancelled visit.",
                 ticket_id="C17", active=active, visit_window="Day2 10:00–12:00", snapshotted_at=at),
            item("coordinator-batch", "C18 archived as duplicate. " +
                 ("C17 remains the Day2 10:00–12:00 visit. No completed repair is recorded."
                  if active else "C17 is closed; its visit is cancelled and C18 archival does not restore it."))],
            set={"case-board":dict(duplicate="closed")}))

    if kind == "lh_visit_result":
        active = resources["actual-appointment"]["active"]
        return dict(effect=dict(add=[item("visit-report",
            ("C17 visit attended 10:00–12:00. Technician tightened hinge temporarily. A replacement bracket still needs "
             "coordinator review/order; no part order or final repair confirmed." if active else
             "C17 was cancelled in the coordinator batch. No technician attendance or temporary work occurred."),
            ticket_id="C17", result="temporary_work" if active else "cancelled")]))

    if kind == "lh_route_send":
        draft = deepcopy(resources["return-selection"]["fields"])
        identifier = "sys-crew-brief-" + str(at)
        brief = item(identifier, draft["text"], "delivery", recipient="two-walking-crew",
                     route=draft["route"], version=identifier, created_at=at)
        return dict(effect=dict(add=[brief], patch={"sent-return":
                    dict(fields=draft, brief_id=identifier, recipient="two-walking-crew",
                         text=draft["text"], sent_at=at)}),
                    facts=dict(delivered_brief=identifier, recipient="two-walking-crew",
                               delivered_text=draft["text"], route_feasibility_audited=False))

    if kind == "lh_return_result":
        route_record = resources["actual-return-route"]
        route = route_record["fields"]["route"]
        descriptions = {
            "Canal": "Two used Garden→Canal→Pier from 10:52, ten plus eight minutes, reaching Pier 11:10.",
            "Mill": "Two reached Mill 10:59, waited for 11:05 entry, then took nine minutes: Pier 11:14.",
            "direct": "Two reached Garden 10:52 after the direct gate closed 10:45; that edge was not entered.",
            "Lookout": "The unstaffed Lookout connector was not traversed; no supported return is recorded."
        }
        report = item("return-report", descriptions[route], source="two-walking-crew",
                      actual_route=route, brief_id=route_record.get("brief_id"),
                      actual_departure="10:52", reported_at=at)
        return dict(effect=dict(add=[report]))

    if kind == "lh_dispatch":
        entries = []
        for source in ("standalone-queue", "weekly-series"):
            fields = resources.get(source, {}).get("fields", {"demo": "on", "payment": "on", "demo_time": "19:00"})
            for topic in ("demo", "payment"):
                if fields[topic] == "on":
                    entries.append(dict(source=source, topic=topic,
                        text=("Demo Day12 at " + fields.get("demo_time", "19:00")
                              if topic == "demo" else "Estimated payment Day20"),
                        source_fields=deepcopy(fields)))
        actual = item("dispatch-record", "Actual immutable dispatch batch. Only listed messages were sent.",
                      entries=entries, recipient="reminder-subscribers", dispatched_at=at)
        added = [actual]
        if entries:
            added.append(item("dispatch-audience", "We received the entries recorded in dispatch-record. "
                              "Which parts remain current?", "dm", author="reminder-subscribers",
                              recipient="reminder-subscribers", dispatch_id="dispatch-record"))
        return dict(effect=dict(add=added), facts=dict(sent_count=len(entries)))

    if kind.startswith("lh_packet_"):
        replacement = kind == "lh_packet_replace"
        content = dict(text=resources["promo-copy"]["text"] if replacement
                       else "Withdraw the earlier packet from upcoming sponsored use.",
                       assets=deepcopy(resources["promo-copy"].get("assets", []))
                       if replacement else [],
                       request_kind="replacement" if replacement else "withdrawal")
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        pid = "sys-lh-packet-" + str(at)
        packet = item(pid, content["text"], "delivery", recipient="gallery-editor",
                      created_at=at, content_sha256=digest, **{k: v for k, v in content.items() if k != "text"})
        receipt = item("sys-editor-received-" + str(at),
                       "I received this exact request for the next processing window. "
                       "Receipt is not final staging or publication. Backups cannot all be erased.",
                       "dm", author="gallery-editor", recipient="gallery-editor",
                       packet_id=pid, content_sha256=digest)
        return dict(effect=dict(add=[packet, receipt], patch={"actual-outbound":
                    dict(**content, packet_id=pid, content_sha256=digest)}),
                    facts=dict(sent_packet_id=pid, content_sha256=digest,
                               recipient="gallery-editor", editorial_processing_completed=False))

    if kind == "lh_editor_process":
        outbound = resources["actual-outbound"]
        if "packet_id" not in outbound:
            state = dict(packet_id="historical-packet", assets=["photo-p", "photo-q"],
                         request_kind="historical", text="Earlier sponsored packet remains staged.")
        else:
            state = {k: deepcopy(outbound[k]) for k in
                     ("packet_id", "assets", "request_kind", "text", "content_sha256")}
        receipt = item("sys-editor-stage-" + str(at),
                       "Actual editorial staging result for the named request. "
                       "This does not grant any image-use permission.",
                       fields=state, created_at=at)
        return dict(effect=dict(add=[receipt], patch={"editor-stage":
                    dict(text="Current actual staged packet.", fields=state)}), facts=state)

    if kind == "lh_import_signup":
        ledger = deepcopy(resources["booking-ledger"]["fields"])
        incoming = resources["incoming-party"]["fields"]
        if ledger["intake_processed"]:
            return dict(facts=dict(processed=False, reason="This batch was already processed."))
        deployed = resources["deployed-form"]
        f = deployed["fields"]
        adults, children = incoming["adults"], incoming["children"]
        counted = children + (adults if f["count_by"] == "people" else 0)
        active = deployed.get("status") == "published" and f.get("intake", "open") == "open"
        accepted = active and counted <= f["remaining_capacity"]
        ledger.update(intake_processed=True, incoming_status="accepted" if accepted else "waitlisted",
                      incoming_people=adults + children if accepted else 0)
        if accepted:
            ledger["confirmed_people"] += adults + children
        copy = item("sys-signup-intake-" + str(at),
                    "Actual private intake record for anonymous party C; not a synthetic preview.",
                    fields=dict(party_id="C", actual_people=adults + children,
                                counted_units=counted, accepted=accepted,
                                private_view=f["attendee_view"] == "private",
                                photo_question=f["photo_question"]))
        return dict(effect=dict(add=[copy], patch={"booking-ledger": {"fields": ledger}}),
                    facts=deepcopy(copy["fields"]))

    if kind == "lh_reserve_staff":
        request = deepcopy(resources["staff-selection"]["fields"])
        roster = resources["standby-record"]["availability"]
        available = roster[request["person"]]
        accepted = (request["role"] in available["roles"] and
                    available["start"] <= request["start"] < request["end"] <= available["end"])
        receipt = item("sys-staff-accepted-" + str(at),
                       ("I accept exactly the requested role and interval. I occupy one chair."
                        if accepted else "I cannot accept this role/interval from my actual availability."),
                       "dm", author="backup-staff-" + request["person"], recipient="backup-staff-" + request["person"],
                       accepted=accepted, request=request, session="Day3 craft afternoon")
        effect = dict(add=[receipt])
        if accepted:
            effect["patch"] = {"actual-backup": dict(fields=request, acceptance_id=receipt["id"],
                text="Actual accepted backup staff "+request["person"]+" for "+request["role"]+
                     " during requested minutes "+str(request["start"])+"–"+str(request["end"])+
                     ". This staff member is distinct from anonymous party-C.")}
        return dict(effect=effect, facts=dict(reservation_recorded=accepted,
                    acceptance_id=receipt["id"], requested=request,
                    full_session_coverage_audited=False))

    if kind == "lh_record_withdrawal":
        ledger = deepcopy(resources["booking-ledger"]["fields"])
        if ledger["a_withdrawal_processed"]:
            return dict(facts=dict(processed=False, reason="Party A withdrawal was already recorded."))
        ledger["a_withdrawal_processed"] = True
        ledger["confirmed_people"] -= 3
        return dict(effect=dict(patch={"booking-ledger": {"fields": ledger}},
                    add=[item("sys-withdrawal-recorded-" + str(at),
                              "Actual party A withdrawal recorded privately. Its three attendance "
                              "places are released. No public image permission was added.",
                              party_id="A", released_people=3)]),
                    facts=dict(released_people=3, public_photo_permission=False))

    raise ValueError("Unknown revision calculator: " + kind)
