"""Audit rules tailored for Laravel and PHP applications."""
import re
from .base import RegexRule

LARAVEL_RULES = [
    RegexRule(
        rule_id='laravel.mass-assignment',
        layer='function',
        title='Mass assignment vulnerability ($guarded = [] or unvalidated request input)',
        severity='high',
        confidence='high',
        pattern=re.compile(r'protected\s+\$guarded\s*=\s*\[\s*\];|::create\(\s*\$request->all\(\)\s*\)'),
        file_patterns=['.php'],
        recommendation='Explicitly define $fillable attributes on Eloquent models or use $request->validated().',
        cwe='CWE-915',
        owasp='A08:2021-Software and Data Integrity Failures',
        stacks={'laravel', 'php'}
    ),
    RegexRule(
        rule_id='laravel.raw-sql-injection',
        layer='database',
        title='Potential SQL injection in raw query method',
        severity='critical',
        confidence='medium',
        pattern=re.compile(r'(?:whereRaw|selectRaw|orderByRaw|havingRaw|DB::raw)\s*\(\s*["\'].*?\$[a-zA-Z_]'),
        file_patterns=['.php'],
        recommendation='Always use parameterized bindings when calling DB::raw or whereRaw methods.',
        cwe='CWE-89',
        owasp='A03:2021-Injection',
        stacks={'laravel', 'php'}
    ),
    RegexRule(
        rule_id='laravel.blade-unescaped-html',
        layer='code',
        title='Unescaped output in Blade template ({!! ... !!})',
        severity='medium',
        confidence='medium',
        pattern=re.compile(r'\{!!\s*\$(?:request|_GET|_POST|[a-zA-Z0-9_>-]+)\s*!!\}'),
        file_patterns=['.blade.php'],
        recommendation='Use escaped Blade syntax {{ ... }} unless rendering sanitized HTML through a trusted cleaner.',
        cwe='CWE-79',
        owasp='A03:2021-Injection',
        stacks={'laravel', 'php'}
    ),
    RegexRule(
        rule_id='laravel.debug-mode-enabled',
        layer='config',
        title='Laravel debug mode explicitly enabled (APP_DEBUG=true)',
        severity='high',
        confidence='high',
        pattern=re.compile(r'(?i)\bAPP_DEBUG\s*=\s*true\b'),
        file_patterns=['.env', 'config/app.php'],
        recommendation='Ensure APP_DEBUG is set to false in all staging and production deployments to prevent stack traces leaking.',
        cwe='CWE-200',
        owasp='A05:2021-Security Misconfiguration',
        stacks={'laravel', 'php'}
    ),
    RegexRule(
        rule_id='laravel.open-route-any',
        layer='function',
        title='Overly permissive HTTP route definition (Route::any)',
        severity='medium',
        confidence='low',
        pattern=re.compile(r'Route::any\s*\('),
        file_patterns=['routes/'],
        recommendation='Specify exact HTTP verbs (get, post, put, delete) for all endpoints instead of Route::any.',
        cwe='CWE-650',
        owasp='A04:2021-Insecure Design',
        stacks={'laravel', 'php'}
    )
]
