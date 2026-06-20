-- 1. 권한(Role) 부여: 익명(anon) 사용자가 테이블에 접근/수정할 수 있도록 허용
GRANT ALL ON sm_svclist TO anon;
GRANT ALL ON sm_svclist TO authenticated;
GRANT ALL ON sm_svclist TO service_role;

-- 2. 혹시 RLS가 활성화된 경우를 대비해 RLS 정책을 추가하거나 강제 비활성화
ALTER TABLE sm_svclist DISABLE ROW LEVEL SECURITY;

-- 3. 안전을 위해 익명 사용자의 모든 작업(조회/수정/삭제/삽입)을 허용하는 정책 추가
CREATE POLICY "Enable all for anon" ON sm_svclist FOR ALL USING (true) WITH CHECK (true);
