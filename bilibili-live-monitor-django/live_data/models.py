from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)

class LiveRoom(models.Model):
    """直播间信息模型"""
    room_id = models.BigIntegerField(unique=True, verbose_name="房间ID", db_index=True)
    title = models.CharField(max_length=255, verbose_name="直播间标题", default="未知标题")
    uname = models.CharField(max_length=100, verbose_name="主播用户名", default="未知主播")
    face = models.URLField(blank=True, null=True, verbose_name="主播头像")
    online = models.IntegerField(default=0, verbose_name="在线人数")
    status = models.IntegerField(default=0, verbose_name="直播状态", 
                               choices=[(0, '未开播'), (1, '直播中'), (2, '轮播')])
    # 为现有数据提供默认值
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "直播间"
        verbose_name_plural = "直播间"
        db_table = 'live_rooms'
        indexes = [
            models.Index(fields=['room_id']),
            models.Index(fields=['status']),
            models.Index(fields=['updated_at']),
        ]
    
    def clean(self):
        """模型验证"""
        if self.room_id <= 0:
            raise ValidationError("房间ID必须大于0")
        if self.online < 0:
            raise ValidationError("在线人数不能为负数")
    
    def __str__(self):
        return f"{self.room_id} - {self.title}"

class DanmakuData(models.Model):
    """弹幕数据模型"""
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, verbose_name="房间", 
                           related_name='danmaku_set')
    uid = models.BigIntegerField(verbose_name="用户UID", db_index=True)
    username = models.CharField(max_length=100, verbose_name="用户名", default="匿名用户")
    message = models.TextField(verbose_name="弹幕内容")
    timestamp = models.DateTimeField(verbose_name="发送时间", db_index=True)
    medal_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="粉丝牌名称")
    medal_level = models.IntegerField(default=0, verbose_name="粉丝牌等级")
    user_level = models.IntegerField(default=0, verbose_name="用户等级")
    is_admin = models.BooleanField(default=False, verbose_name="是否管理员")
    is_vip = models.BooleanField(default=False, verbose_name="是否VIP")
    # 修改：为现有数据提供默认值，新数据将使用创建时的时间
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        verbose_name = "弹幕数据"
        verbose_name_plural = "弹幕数据"
        db_table = 'danmaku_data'
        indexes = [
            models.Index(fields=['room', 'timestamp']),
            models.Index(fields=['uid']),
            models.Index(fields=['username']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['created_at']),
        ]
        # 添加复合唯一约束，防止重复数据
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'uid', 'message', 'timestamp'], 
                name='unique_danmaku'
            )
        ]
    
    def clean(self):
        """模型验证"""
        if not self.message.strip():
            raise ValidationError("弹幕内容不能为空")
        if self.medal_level < 0:
            raise ValidationError("粉丝牌等级不能为负数")
        if self.user_level < 0:
            raise ValidationError("用户等级不能为负数")
    
    def save(self, *args, **kwargs):
        """保存时设置创建时间（如果是新记录）"""
        if not self.pk and not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.username}: {self.message[:20]}{'...' if len(self.message) > 20 else ''}"

class GiftData(models.Model):
    """礼物数据模型"""
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, verbose_name="房间",
                           related_name='gift_set')
    uid = models.BigIntegerField(verbose_name="用户UID", db_index=True)
    username = models.CharField(max_length=100, verbose_name="用户名", default="匿名用户")
    gift_name = models.CharField(max_length=100, verbose_name="礼物名称")
    gift_id = models.IntegerField(verbose_name="礼物ID", db_index=True)
    num = models.IntegerField(verbose_name="礼物数量", default=1)
    price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="礼物单价", default=0)
    total_price = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name="总价值")
    timestamp = models.DateTimeField(verbose_name="发送时间", db_index=True)
    medal_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="粉丝牌名称")
    medal_level = models.IntegerField(default=0, verbose_name="粉丝牌等级")
    # 修改：为现有数据提供默认值，新数据将使用创建时的时间
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    def clean(self):
        """模型验证"""
        if self.num <= 0:
            raise ValidationError("礼物数量必须大于0")
        if self.price < 0:
            raise ValidationError("礼物单价不能为负数")
        if self.medal_level < 0:
            raise ValidationError("粉丝牌等级不能为负数")
    
    def save(self, *args, **kwargs):
        """保存时自动计算总价值和设置创建时间"""
        try:
            # 设置创建时间（如果是新记录）
            if not self.pk and not self.created_at:
                self.created_at = timezone.now()
            
            # 确保数据类型正确
            if isinstance(self.price, (int, float)):
                self.price = Decimal(str(self.price))
            if isinstance(self.num, str):
                self.num = int(self.num)
            
            # 计算总价值
            if self.total_price == 0 or not self.total_price:
                self.total_price = self.price * self.num
            
            # 调用clean方法进行验证
            self.clean()
            
        except (ValueError, TypeError, ValidationError) as e:
            logger.error(f"保存礼物数据时出错: {e}")
            # 设置安全的默认值
            if self.total_price == 0:
                self.total_price = Decimal('0.0000')
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "礼物数据"
        verbose_name_plural = "礼物数据"
        db_table = 'gift_data'
        indexes = [
            models.Index(fields=['room', 'timestamp']),
            models.Index(fields=['uid']),
            models.Index(fields=['username']),
            models.Index(fields=['gift_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['total_price']),
            models.Index(fields=['created_at']),
        ]
        # 添加复合唯一约束，防止重复数据
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'uid', 'gift_id', 'timestamp'], 
                name='unique_gift'
            )
        ]
    
    def __str__(self):
        return f"{self.username}: {self.gift_name} x{self.num} (¥{self.total_price})"

class MonitoringTask(models.Model):
    """监控任务模型"""
    STATUS_CHOICES = [
        ('stopped', '已停止'),
        ('running', '运行中'),
        ('paused', '已暂停'),
        ('error', '错误'),
    ]
    
    task_name = models.CharField(max_length=100, verbose_name="任务名称", unique=True)
    room_ids = models.TextField(verbose_name="监控房间ID列表", default='[]')  # JSON格式存储
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                            default='stopped', verbose_name="任务状态")
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    collected_danmaku = models.IntegerField(default=0, verbose_name="收集弹幕数")
    collected_gifts = models.IntegerField(default=0, verbose_name="收集礼物数")
    error_count = models.IntegerField(default=0, verbose_name="错误次数")
    last_error = models.TextField(blank=True, null=True, verbose_name="最近错误")
    # 修改：为现有数据提供默认值，新数据将使用创建时的时间
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    def clean(self):
        """模型验证"""
        if not self.task_name.strip():
            raise ValidationError("任务名称不能为空")
        
        # 验证room_ids是否为有效JSON
        try:
            room_list = json.loads(self.room_ids)
            if not isinstance(room_list, list):
                raise ValidationError("房间ID列表必须是数组格式")
            # 验证每个房间ID都是整数
            for room_id in room_list:
                if not isinstance(room_id, int) or room_id <= 0:
                    raise ValidationError(f"无效的房间ID: {room_id}")
        except json.JSONDecodeError:
            raise ValidationError("房间ID列表必须是有效的JSON格式")
        
        if self.collected_danmaku < 0:
            raise ValidationError("收集弹幕数不能为负数")
        if self.collected_gifts < 0:
            raise ValidationError("收集礼物数不能为负数")
        if self.error_count < 0:
            raise ValidationError("错误次数不能为负数")
    
    def get_room_ids(self):
        """获取房间ID列表"""
        try:
            room_list = json.loads(self.room_ids)
            return room_list if isinstance(room_list, list) else []
        except (json.JSONDecodeError, TypeError):
            logger.error(f"解析room_ids失败: {self.room_ids}")
            return []
    
    def set_room_ids(self, room_list):
        """设置房间ID列表"""
        if not isinstance(room_list, list):
            raise ValueError("room_list必须是列表类型")
        
        # 验证每个房间ID
        validated_list = []
        for room_id in room_list:
            try:
                validated_id = int(room_id)
                if validated_id > 0:
                    validated_list.append(validated_id)
            except (ValueError, TypeError):
                logger.warning(f"跳过无效的房间ID: {room_id}")
        
        self.room_ids = json.dumps(validated_list)
    
    def get_danmaku_count(self):
        """获取收集的弹幕数量"""
        return self.collected_danmaku
    
    def get_gift_count(self):
        """获取收集的礼物数量"""
        return self.collected_gifts
    
    def get_room_count(self):
        """获取监控房间数量"""
        return len(self.get_room_ids())
    
    def get_runtime(self):
        """获取运行时间"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return timezone.now() - self.start_time
        return None
    
    def get_success_rate(self):
        """获取成功率"""
        total = self.collected_danmaku + self.collected_gifts
        if total > 0 and self.error_count >= 0:
            return max(0, ((total - self.error_count) / total) * 100)
        return 100.0 if total > 0 else 0.0
    
    def save(self, *args, **kwargs):
        """保存前验证并设置创建时间"""
        if not self.pk and not self.created_at:
            self.created_at = timezone.now()
        self.clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "监控任务"
        verbose_name_plural = "监控任务"
        db_table = 'monitoring_tasks'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
    
    def __str__(self):
        return f"{self.task_name} - {self.get_status_display()}"

class DataMigrationLog(models.Model):
    """数据迁移日志"""
    MIGRATION_TYPE_CHOICES = [
        ('danmaku', '弹幕数据'),
        ('gift', '礼物数据'),
        ('room', '房间数据'),
        ('all', '全部数据'),
    ]
    
    STATUS_CHOICES = [
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('partial', '部分成功'),
    ]
    
    migration_type = models.CharField(max_length=20, choices=MIGRATION_TYPE_CHOICES, 
                                    verbose_name="迁移类型")
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    total_records = models.IntegerField(default=0, verbose_name="总记录数")
    success_records = models.IntegerField(default=0, verbose_name="成功记录数")
    failed_records = models.IntegerField(default=0, verbose_name="失败记录数")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                            default='running', verbose_name="状态")
    error_message = models.TextField(blank=True, null=True, verbose_name="错误信息")
    # 修改：为现有数据提供默认值，新数据将使用创建时的时间
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    
    def clean(self):
        """模型验证"""
        if self.total_records < 0:
            raise ValidationError("总记录数不能为负数")
        if self.success_records < 0:
            raise ValidationError("成功记录数不能为负数")
        if self.failed_records < 0:
            raise ValidationError("失败记录数不能为负数")
        if self.success_records + self.failed_records > self.total_records:
            raise ValidationError("成功数和失败数之和不能超过总记录数")
    
    def get_duration(self):
        """获取执行时长"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return timezone.now() - self.start_time
        return None
    
    def get_success_rate(self):
        """获取成功率"""
        if self.total_records > 0:
            return (self.success_records / self.total_records) * 100
        return 0.0
    
    def save(self, *args, **kwargs):
        """保存前验证并设置创建时间"""
        if not self.pk and not self.created_at:
            self.created_at = timezone.now()
        self.clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "数据迁移日志"
        verbose_name_plural = "数据迁移日志"
        db_table = 'data_migration_logs'
        indexes = [
            models.Index(fields=['migration_type']),
            models.Index(fields=['status']),
            models.Index(fields=['start_time']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_migration_type_display()} - {self.get_status_display()} - {self.start_time}"