from django.db import models
from django.utils import timezone

class LiveRoom(models.Model):
    """直播房间模型"""
    room_id = models.IntegerField(unique=True, verbose_name="房间ID")
    uname = models.CharField(max_length=100, verbose_name="主播用户名")
    title = models.CharField(max_length=200, verbose_name="直播间标题")
    area_name = models.CharField(max_length=50, blank=True, verbose_name="分区名称")
    parent_area_name = models.CharField(max_length=50, blank=True, verbose_name="父分区名称")
    live_status = models.IntegerField(default=0, verbose_name="直播状态")  # 0:未开播, 1:直播中
    popularity = models.IntegerField(default=0, verbose_name="人气值")
    is_monitoring = models.BooleanField(default=False, verbose_name="是否监控中")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "直播房间"
        verbose_name_plural = "直播房间"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.uname} ({self.room_id})"

class DanmakuData(models.Model):
    """弹幕数据模型"""
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, verbose_name="所属房间")
    username = models.CharField(max_length=100, verbose_name="用户名")
    uid = models.BigIntegerField(verbose_name="用户ID")
    message = models.TextField(verbose_name="弹幕内容")
    send_time = models.DateTimeField(verbose_name="发送时间")
    send_time_timestamp = models.BigIntegerField(verbose_name="发送时间戳")
    received_at = models.DateTimeField(default=timezone.now, verbose_name="接收时间")
    
    class Meta:
        verbose_name = "弹幕数据"
        verbose_name_plural = "弹幕数据"
        ordering = ['-send_time']
        indexes = [
            models.Index(fields=['room', '-send_time']),
            models.Index(fields=['username']),
            models.Index(fields=['send_time']),
        ]
    
    def __str__(self):
        return f"{self.username}: {self.message[:50]}"

class GiftData(models.Model):
    """礼物数据模型"""
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, verbose_name="所属房间")
    username = models.CharField(max_length=100, verbose_name="用户名")
    gift_name = models.CharField(max_length=100, verbose_name="礼物名称")
    gift_id = models.IntegerField(verbose_name="礼物ID")
    num = models.IntegerField(default=1, verbose_name="礼物数量")
    price = models.IntegerField(default=0, verbose_name="礼物价格")
    coin_type = models.CharField(max_length=20, default='silver', verbose_name="货币类型")  # gold/silver
    send_time = models.DateTimeField(verbose_name="发送时间")
    received_at = models.DateTimeField(default=timezone.now, verbose_name="接收时间")
    
    class Meta:
        verbose_name = "礼物数据"
        verbose_name_plural = "礼物数据"
        ordering = ['-send_time']
        indexes = [
            models.Index(fields=['room', '-send_time']),
            models.Index(fields=['username']),
            models.Index(fields=['gift_name']),
        ]
    
    def __str__(self):
        return f"{self.username} -> {self.gift_name} x{self.num}"

class MonitoringTask(models.Model):
    """监控任务模型"""
    room = models.ForeignKey(LiveRoom, on_delete=models.CASCADE, verbose_name="监控房间")
    task_id = models.CharField(max_length=100, unique=True, verbose_name="任务ID")
    status = models.CharField(max_length=20, default='pending', verbose_name="任务状态")  # pending/running/stopped/error
    start_time = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    danmaku_count = models.IntegerField(default=0, verbose_name="收集弹幕数")
    gift_count = models.IntegerField(default=0, verbose_name="收集礼物数")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "监控任务"
        verbose_name_plural = "监控任务"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"任务{self.task_id} - {self.room.uname}"