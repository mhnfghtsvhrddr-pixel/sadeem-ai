"""
═══════════════════════════════════════════════════════════════
🦷 SADEEM AI - Dental Clinic Appointment Agent
   سديم AI - وكيل حجز مواعيد عيادة الأسنان
   SignalWire Agents SDK
═══════════════════════════════════════════════════════════════
"""

from signalwire.ai_agent import AgentBase, FunctionResult
from datetime import datetime
import secrets

# ═══════════════════════════════════════════════════════════
# 🗄️ قاعدة البيانات
# ═══════════════════════════════════════════════════════════

PATIENTS_DB = {
    "+966501234567": {"name": "محمد العتيبي", "visits": 3, "last_visit": "2024-01-15"},
    "+966509876543": {"name": "سارة القحطاني", "visits": 5, "last_visit": "2024-01-20"},
}

TIME_SLOTS = {
    "الأحد":    ["9:00 ص", "10:00 ص", "11:00 ص", "1:00 م", "4:00 م", "5:00 م", "7:00 م"],
    "الإثنين":  ["9:00 ص", "10:00 ص", "12:00 م", "2:00 م", "3:00 م", "6:00 م", "8:00 م"],
    "الثلاثاء": ["8:00 ص", "9:00 ص", "11:00 ص", "3:00 م", "4:00 م", "5:00 م", "7:00 م"],
    "الأربعاء": ["10:00 ص", "11:00 ص", "12:00 م", "2:00 م", "5:00 م", "6:00 م", "8:00 م"],
    "الخميس":   ["9:00 ص", "10:00 ص", "1:00 م", "3:00 م", "4:00 م", "6:00 م", "7:00 م"],
}

SERVICES = {
    "كشف": 100, "تنظيف": 200, "حشو": 350,
    "تقويم": 5000, "زراعة": 4000, "علاج_جذور": 800,
    "تبييض": 1200, "أطفال": 150, "طارئ": 250,
}

booked_appointments = []


# ═══════════════════════════════════════════════════════════
# 🤖 سديم - الوكيل الرئيسي
# ═══════════════════════════════════════════════════════════

class SadeemAgent(AgentBase):
    """وكيل سديم لاستقبال عيادة الأسنان"""
    
    def __init__(self):
        super().__init__(
            name="sadeem-dental-agent",
            route="/dental",
            port=3000
        )
        self._init_sadeem()
    
    def _init_sadeem(self):
        """تهيئة سديم"""
        self.set_prompt_text("""
أنت "سديم"، وكيلة الاستقبال في "مركز الابتسامة لطب الأسنان".

[المرحلة 1 - الاستقبال]
1. اسألي عن رقم الجوال
2. استخدمي lookup_patient للبحث
3. استخدمي get_available_slots فوراً

[المرحلة 2 - التفاعل]
1. اعرضي المواعيد المتاحة
2. احجزي باستخدام add_appointment
3. ⚠️ إذا لم تفهمي بعد محاولتين: transfer_to_human فوراً

[المرحلة 3 - الإغلاق]
1. أرسلي send_confirmation_sms
2. زودي المريض بكود الإلغاء

🚫 لا تحجزي في وقت محجوز
🚫 استفسارات طبية = transfer_to_human فوراً
""")
        
        self.add_language(
            "Arabic", "ar-SA", "rime.spore",
            speech_fillers=["لحظة من فضلك..."],
            function_fillers=["جاري فتح جدول المواعيد..."]
        )
        
        self.set_params({
            "temperature": 0.2,
            "end_of_speech_timeout": 1000,
            "attention_timeout": 15000,
        })
    
    def _normalize_day(self, day):
        """توحيد أسماء الأيام"""
        day_map = {
            "الاحد": "الأحد", "الأحد": "الأحد",
            "الاثنين": "الإثنين", "الإثنين": "الإثنين",
            "الثلاثاء": "الثلاثاء", "الاربعاء": "الأربعاء",
            "الأربعاء": "الأربعاء", "الخميس": "الخميس",
        }
        return day_map.get(day, day)
    
    def _get_available(self, day):
        """جلب الأوقات المتاحة"""
        day = self._normalize_day(day)
        if day not in TIME_SLOTS:
            return []
        all_times = TIME_SLOTS[day]
        booked = [b["time"] for b in booked_appointments 
                 if b["day"] == day and b["status"] == "مؤكد"]
        return [t for t in all_times if t not in booked]


# ═══════════════════════════════════════════════════════════
# 🏗️ إنشاء سديم
# ═══════════════════════════════════════════════════════════

sadeem = SadeemAgent()


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 1: البحث عن مريض
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="lookup_patient", description="البحث عن مريض برقم الهاتف")
def lookup_patient(args, raw_data=None):
    """🔍 البحث في سجلات المرضى"""
    phone = args.get("phone", "").replace(" ", "").replace("-", "")
    
    if not phone:
        return FunctionResult("أحتاج رقم الجوال للبحث. ما هو رقمك؟")
    
    patient = PATIENTS_DB.get(phone)
    
    if patient:
        return FunctionResult(
            f"✅ أهلاً بك {patient['name']}! "
            f"لديك {patient['visits']} زيارات سابقة. "
            f"آخر زيارة: {patient.get('last_visit', 'غير متوفر')}.\n"
            f"كيف يمكنني مساعدتك اليوم؟"
        ).update_global_data({
            "patient_name": patient["name"],
            "patient_phone": phone,
            "is_returning": True,
            "attempt_count": 0,
        })
    else:
        return FunctionResult(
            "👋 أهلاً بك! هذه زيارتك الأولى لمركز الابتسامة. "
            "ما هو اسمك الكريم؟"
        ).update_global_data({
            "patient_phone": phone,
            "is_returning": False,
            "attempt_count": 0,
        })


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 2: جلب المواعيد
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="get_available_slots", description="جلب المواعيد المتاحة ليوم محدد")
def get_available_slots(args, raw_data=None):
    """🗓️ جلب المواعيد المتاحة"""
    day = sadeem._normalize_day(args.get("day", ""))
    
    if day in ["الجمعة", "السبت"]:
        return FunctionResult(
            "🏠 العيادة مغلقة الجمعة والسبت.\n"
            "أيام العمل: الأحد إلى الخميس. أي يوم تفضل؟"
        )
    
    available = sadeem._get_available(day)
    
    if not available:
        return FunctionResult(
            f"⚠️ جميع مواعيد {day} محجوزة.\n"
            "الأيام المتاحة: الأحد، الإثنين، الثلاثاء، الأربعاء، الخميس.\n"
            "هل تريد تجربة يوم آخر؟"
        )
    
    times_list = "\n".join([f"   {t}" for t in available])
    
    return FunctionResult(
        f"📅 مواعيد {day} المتاحة:\n\n{times_list}\n\nأي وقت تفضل؟"
    ).update_global_data({
        "current_day": day,
        "available_slots": available,
        "schedule_loaded": True,
    })


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 3: حجز موعد
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="add_appointment", description="حجز موعد جديد مع التحقق من التفرغ")
def add_appointment(args, raw_data=None):
    """📝 حجز موعد"""
    global_data = raw_data.get("global_data", {}) if raw_data else {}
    
    patient_name = args.get("patient_name") or global_data.get("patient_name", "")
    phone = args.get("phone") or global_data.get("patient_phone", "")
    day = sadeem._normalize_day(args.get("day", ""))
    time = args.get("time", "")
    service = args.get("service", "كشف")
    
    # تحقق من البيانات
    if not all([patient_name, phone, day, time]):
        return FunctionResult("❌ لا يمكن إتمام الحجز. بيانات ناقصة.")
    
    # تحقق من توفر الوقت
    available = sadeem._get_available(day)
    if time not in available:
        alternatives = "\n".join([f"   • {t}" for t in available[:5]])
        return FunctionResult(
            f"⚠️ عذراً {patient_name}، {time} غير متاح.\n\n"
            f"البدائل في {day}:\n{alternatives}\n\nأي وقت تفضل؟"
        )
    
    # تحقق من الاستفسارات الطبية
    medical_words = ["استشارة", "نصيحة", "تشخيص", "دواء", "وصفة", "ألم", "وجع"]
    if any(w in service for w in medical_words):
        return FunctionResult("هذا استفسار طبي، سأحولك للطبيب فوراً.")
    
    # إنشاء كود إلغاء
    code = secrets.token_hex(4).upper()
    
    # حفظ الموعد
    appointment = {
        "id": f"APT-{len(booked_appointments)+1:04d}",
        "patient_name": patient_name,
        "phone": phone,
        "day": day,
        "time": time,
        "service": service,
        "cancellation_code": code,
        "created_at": datetime.now().isoformat(),
        "status": "مؤكد",
    }
    booked_appointments.append(appointment)
    
    price = SERVICES.get(service, 0)
    
    return FunctionResult(
        f"✅ تم حجز موعدك {patient_name}!\n\n"
        f"📅 {day} ⏰ {time}\n"
        f"🦷 {service}\n"
        f"💰 التكلفة التقريبية: {price} ريال\n\n"
        f"🔑 كود الإلغاء: {code}\n"
        f"احتفظ بهذا الكود."
    ).update_global_data({
        "current_cancellation_code": code,
        "booking_success": True,
    })


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 4: إرسال SMS
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="send_confirmation_sms", description="إرسال رسالة تأكيد مع كود الإلغاء")
def send_confirmation_sms(args, raw_data=None):
    """📱 إرسال تأكيد"""
    global_data = raw_data.get("global_data", {}) if raw_data else {}
    
    phone = args.get("phone") or global_data.get("patient_phone", "")
    patient_name = args.get("patient_name") or global_data.get("patient_name", "المريض")
    code = args.get("code") or global_data.get("current_cancellation_code", "")
    
    if not phone or not code:
        return FunctionResult("❌ لا يمكن الإرسال. بيانات غير مكتملة.")
    
    # البحث عن الموعد
    booking = None
    for b in reversed(booked_appointments):
        if b["phone"] == phone and b["status"] == "مؤكد":
            booking = b
            break
    
    if not booking:
        return FunctionResult("❌ لم أجد موعداً مؤكداً.")
    
    message = (
        f"🦷 مركز الابتسامة لطب الأسنان\n"
        f"✅ تأكيد موعد\n"
        f"👤 {patient_name}\n"
        f"📅 {booking['day']} ⏰ {booking['time']}\n"
        f"🦷 {booking.get('service', 'كشف')}\n"
        f"🔑 كود الإلغاء: {code}\n"
        f"📞 920000000"
    )
    
    return FunctionResult(
        f"📱 تم إرسال التأكيد إلى {phone}\n🔑 كودك: {code}"
    ).send_sms(
        to_number=phone,
        from_number="+966500000000",
        body=message,
        tags=["appointment", "dental"]
    )


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 5: استعلام عن المواعيد
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="check_appointment", description="الاستعلام عن المواعيد المحجوزة")
def check_appointment(args, raw_data=None):
    """🔍 استعلام"""
    phone = args.get("phone", "")
    
    found = [b for b in booked_appointments 
             if b["phone"] == phone and b["status"] == "مؤكد"]
    
    if not found:
        return FunctionResult("📭 لا توجد مواعيد مؤكدة.")
    
    result = "📋 مواعيدك:\n\n"
    for b in found:
        result += f"🔹 {b['day']} ⏰ {b['time']} - {b['service']} (كود: {b['cancellation_code']})\n"
    
    return FunctionResult(result)


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 6: إلغاء موعد
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="cancel_appointment", description="إلغاء موعد بكود الإلغاء")
def cancel_appointment(args, raw_data=None):
    """❌ إلغاء"""
    code = args.get("code", "").upper()
    phone = args.get("phone", "")
    
    for b in booked_appointments:
        if b["status"] != "مؤكد":
            continue
        if (code and b.get("cancellation_code") == code) or \
           (phone and b["phone"] == phone):
            b["status"] = "ملغي"
            return FunctionResult(
                f"✅ تم إلغاء موعد {b['day']} {b['time']}\nهل تريد الحجز في وقت آخر؟"
            ).send_sms(
                to_number=b["phone"],
                from_number="+966500000000",
                body=f"🦷 مركز الابتسامة\n❌ تم إلغاء موعد {b['day']} {b['time']}\n📞 920000000"
            )
    
    return FunctionResult("❌ لم أجد موعداً للإلغاء. تأكد من الكود.")


# ═══════════════════════════════════════════════════════════
# 🔧 الأداة 7: تحويل للموظف
# ═══════════════════════════════════════════════════════════

@sadeem.tool(name="transfer_to_human", description="[نقطة أمان] تحويل فوري للموظف البشري")
def transfer_to_human(args, raw_data=None):
    """👨‍💼 نقطة الأمان"""
    return FunctionResult(
        "جاري تحويلك لموظف الاستقبال... شكراً لاتصالك!"
    ).connect("+966500000000", final=True)


# ═══════════════════════════════════════════════════════════
# 🚀 تشغيل سديم
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("🦷 مركز الابتسامة لطب الأسنان")
    print("   سديم AI - وكيل الحجز الذكي")
    print("=" * 50)
    print("✅ الوكيل: http://0.0.0.0:3000/dental")
    print("📋 الأدوات: lookup_patient, get_available_slots,")
    print("   add_appointment, send_confirmation_sms,")
    print("   check_appointment, cancel_appointment,")
    print("   transfer_to_human")
    print("=" * 50)
    
    sadeem.serve()
