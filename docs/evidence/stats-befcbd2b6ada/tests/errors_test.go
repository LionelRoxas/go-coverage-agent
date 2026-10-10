package stats

import (
	"testing"
)

func TestStatsError_Error(t *testing.T) {
	cases := []struct {
		name   string
		errMsg string
	}{
		{"empty", ""},
		{"simple", "some error"},
		{"unicode", "错误"},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			se := statsError{err: tc.errMsg}
			if got := se.Error(); got != tc.errMsg {
				t.Errorf("Error() = %q, want %q", got, tc.errMsg)
			}
			var err error = se
			if err.Error() != tc.errMsg {
				t.Errorf("error interface Error() = %q, want %q", err.Error(), tc.errMsg)
			}
		})
	}
}

func TestStatsError_String(t *testing.T) {
	cases := []struct {
		name   string
		errMsg string
	}{
		{"empty", ""},
		{"simple", "another error"},
		{"unicode", "エラー"},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			se := statsError{err: tc.errMsg}
			if got := se.String(); got != tc.errMsg {
				t.Errorf("String() = %q, want %q", got, tc.errMsg)
			}
		})
	}
}
