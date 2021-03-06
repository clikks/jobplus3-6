#!/usr/bin/env python3
# encoding: utf-8

from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from jobplus.decorators import company_required, roles_required
from jobplus.models import Job, User, db, Delivery, Resume,\
                           STATUS_REJECTED, STATUS_ACCEPTED, STATUS_SENT

from jobplus.forms import JobForm

job = Blueprint('job', __name__, url_prefix='/job')


@job.route('/')
def list():
    page = request.args.get('page', default=1, type=int)
    pagination = Job.query.paginate(
        page=page,
        per_page=current_app.config['INDEX_PER_PAGE'],
        error_out=False
    )
    # lists = Job.query.all()
    # newest_jobs = Job.query.order_by(db.desc(Job.created_at)).limit(9).all()
    return render_template('job/list.html', pagination=pagination)


@job.route('/<int:job_id>')
def detail(job_id):
    return render_template('job/detail.html', job=Job.query.get_or_404(job_id))


@job.route('/<int:job_id>/apply')
@login_required
@roles_required(User.ROLE_SEEKER)
def apply(job_id):
    job = Job.query.get_or_404(job_id)
    resume = Resume.query.filter_by(user_id=current_user.id).first()
    if resume is None:
        flash('请上传简历后再投递', 'danger')
    elif resume:
        flash('已经投递过该职位', 'danger')
    else:
        d = Delivery(
            resume_id=resume.id,
            job_id=job.id,
            company_id=job.company.id,
            status=1
        )
        db.session.add(d)
        db.session.commit()
        flash('投递成功', 'success')
    return render_template('job/detail.html', job=job)


@job.route('/<int:job_id>/enable')
@roles_required(User.ROLE_COMPANY, User.ROLE_ADMIN)
def enable(job_id):
    """
    职位状态切换视图，页面渲染时建议使用 next=url_for('some_view') 指定执行后的页面
    :param job_id: 职位id
    :return:
    """
    tar_job = Job.query.filter_by(id=job_id).first()
    if tar_job:
        if tar_job.status == Job.STATUS_CLOSED:
            tar_job.status = Job.STATUS_OPENED
            db.session.add(tar_job)
            db.session.commit()
            flash('职位{} 开始招聘'.format(tar_job.title), 'success')
    else:
        abort(404)
    return redirect(request.args.get('next') or url_for('job.detail', job_id=job_id) or url_for('front.index'))


@job.route('/<int:job_id>/disable')
@roles_required(User.ROLE_COMPANY, User.ROLE_ADMIN)
def disable(job_id):
    """
    职位状态切换视图，页面渲染时建议使用 next=url_for('some_view') 指定执行后的页面
    :param job_id: 职位id
    :return:
    """
    tar_job = Job.query.filter_by(id=job_id).first()
    if tar_job:
        if tar_job.status == Job.STATUS_OPENED:
            tar_job.status = Job.STATUS_CLOSED
            db.session.add(tar_job)
            db.session.commit()
            flash('职位{} 结束招聘'.format(tar_job.title), 'warning')
    else:
        abort(404)
    return redirect(request.args.get('next') or url_for('job.detail', job_id=job_id) or url_for('front.index'))


@job.route('/admin')
@company_required
def job_admin():
    page = request.args.get('page', default=1, type=int)
    filters = {
        Job.company_id == current_user.company_info.id,
        Job.status != Job.STATUS_DELETE,
    }
    pagination = Job.query.filter(*filters).order_by(Job.updated_at.desc()).paginate(
        page=page,
        per_page=current_app.config['LIST_PER_PAGE'],
        error_out=False
    )
    return render_template('job/admin/jobs.html', pagination=pagination)


@job.route('/online')
@company_required
def online_job():
    page = request.args.get('page', default=1, type=int)
    filters = {
        Job.company_id == current_user.company_info.id,
        Job.status == Job.STATUS_OPENED,
    }
    pagination = Job.query.filter(*filters).order_by(Job.updated_at.desc()).paginate(
        page=page,
        per_page=current_app.config['LIST_PER_PAGE'],
        error_out=False
    )
    return render_template('job/admin/online.html', pagination=pagination)


@job.route('/offline')
@company_required
def offline_job():
    page = request.args.get('page', default=1, type=int)
    filters = {
        Job.company_id == current_user.company_info.id,
        Job.status == Job.STATUS_CLOSED,
    }
    pagination = Job.query.filter(*filters).order_by(Job.updated_at.desc()).paginate(
        page=page,
        per_page=current_app.config['LIST_PER_PAGE'],
        error_out=False
    )
    return render_template('job/admin/offline.html', pagination=pagination)


@job.route('/status/<int:job_id>')
@company_required
def job_status(job_id):
    job = Job.query.get_or_404(job_id)
    company = job.company
    online = Job.STATUS_OPENED
    offline = Job.STATUS_CLOSED
    if job.status == online:
        job.status = offline
    elif job.status == offline:
        job.status = online
        company.updated_at = datetime.utcnow()
        db.session.add(company)
    db.session.add(job)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('操作失败，请重试', 'warning')
    finally:
        return redirect(request.referrer)


@job.route('/<int:job_id>/delete')
@company_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    job.status = Job.STATUS_DELETE
    db.session.add(job)
    db.session.commit()
    flash('删除成功', 'success')
    return redirect(request.referrer)


@job.route('/new', methods=['GET', 'POST'])
@company_required
def add_job():
    form = JobForm()
    if form.validate_on_submit():
        form.new_job(current_user.id, current_user.company_info.id)
        flash('增加职位成功', 'success')
        return redirect(url_for('job.job_admin'))
    return render_template('job/admin/add_job.html', form=form)


@job.route('/<int:job_id>/edit', methods=['GET', 'POST'])
@company_required
def edit_job(job_id):
    job = Job.query.get_or_404(job_id)
    form = JobForm(obj=job)
    if form.validate_on_submit():
        form.update_job(job)
        flash('更新成功', 'success')
        return redirect(url_for('job.job_admin', job_id=job.id))
    return render_template('job/admin/edit_job.html', form=form, job=job)


@job.route('/apply/todolist')
@company_required
def todolist():
    page = request.args.get('page', default=1, type=int)
    filters = {
        Delivery.company_id == current_user.company_info.id,
        Delivery.status == STATUS_SENT,
    }
    pagination = Delivery.query.filter(*filters).paginate(
        page=page,
        per_page=current_app.config['LIST_PER_PAGE'],
        error_out=False
    )
    return render_template('job/admin/todolist.html', pagination=pagination)


@job.route('/apply/reject')
@company_required
def reject():
    delivery_id = request.args.get('delivery')
    delivery = Delivery.query.filter_by(id=delivery_id).first()
    delivery.status = STATUS_REJECTED
    db.session.add(delivery)
    db.session.commit()
    return redirect(request.referrer)


@job.route('/apply/interview')
@company_required
def interview():
    delivery_id = request.args.get('delivery')
    delivery = Delivery.query.filter_by(id=delivery_id).first()
    delivery.status = STATUS_ACCEPTED
    db.session.add(delivery)
    db.session.commit()
    return redirect(request.referrer)


@job.route('/apply/interviewlist')
@company_required
def interviewlist():
    page = request.args.get('page', default=1, type=int)
    filters = {
        Delivery.company_id == current_user.company_info.id,
        Delivery.status == STATUS_ACCEPTED,
    }
    pagination = Delivery.query.filter(*filters).paginate(
        page=page,
        per_page=current_app.config['LIST_PER_PAGE'],
        error_out=False
    )
    return render_template('job/admin/interviewlist.html', pagination=pagination)


@job.route('/apply/rejectlist')
@company_required
def rejectlist():
    page = request.args.get('page', default=1, type=int)
    filters = {
        Delivery.company_id == current_user.company_info.id,
        Delivery.status == STATUS_REJECTED,
    }
    pagination = Delivery.query.filter(*filters).paginate(
        page=page,
        per_page=current_app.config['LIST_PER_PAGE'],
        error_out=False
    )
    return render_template('job/admin/rejectlist.html', pagination=pagination)
