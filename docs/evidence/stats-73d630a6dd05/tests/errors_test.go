package stats

import (
	"fmt"
	"testing"
)

func TestError_Method(t *testing.T) {
	cases := []struct {
		name string
		msg  string
	}{
		{"empty", ""},
		{"simple", "something went wrong"},
		{"unicode", "错误"},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			e := statsError{err: tc.msg}
			if got := e.Error(); got != tc.msg {
				t.Fatalf("Error() = %q, want %q", got, tc.msg)
			}
			var err error = e
			if err.Error() != tc.msg {
				t.Fatalf("error interface Error() = %q, want %q", err.Error(), tc.msg)
			}
		})
	}
}

func TestString_Method(t *testing.T) {
	cases := []struct {
		name string
		msg  string
	}{
		{"empty", ""},
		{"simple", "another error"},
		{"unicode", "エラー"},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			e := statsError{err: tc.msg}
			if got := e.String(); got != tc.msg {
				t.Fatalf("String() = %q, want %q", got, tc.msg)
			}
			if fmtStr := fmt.Sprintf("%s", e); fmtStr != tc.msg {
				t.Fatalf("fmt.Sprintf(\"%%s\", e) = %q, want %q", fmtStr, tc.msg)
			}
		})
	}
}
